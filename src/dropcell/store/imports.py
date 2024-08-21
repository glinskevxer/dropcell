"""The import ledger, which is what stops the same file landing twice.

Field data arrives by email, on a memory stick, and again a fortnight later
when somebody forwards the same message. Loading a close interval survey twice
does not simply double the rows. It doubles the length of every under criterion
section, doubles the reported extent of the problem, and produces a report that
is wrong in the direction that gets money spent.

The ledger keys on the hash of the bytes, so the second copy of a file is
recognised however it was named and whoever sent it. A file with one reading
corrected is a different file and lands normally, which is correct: it is
different data and the register should hold it.

The quarantined rows are kept with the run rather than thrown away. Somebody
has to be able to answer what happened to the missing forty rows six months
later, and by then the original file is on a memory stick in a van.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass

from dropcell.errors import ConflictError, NotFoundError
from dropcell.ingest.reader import QuarantinedRow, ReadResult, RowError
from dropcell.store.database import Database


@dataclass(frozen=True)
class ImportRun:
    """One file that was loaded, or refused for being a duplicate."""

    run_id: int
    content_hash: str
    profile: str
    kind: str
    source: str
    imported_at: dt.datetime
    accepted: int
    rejected: int

    @property
    def total(self) -> int:
        """How many data rows the file held."""
        return self.accepted + self.rejected


def row_to_run(row: sqlite3.Row) -> ImportRun:
    """Rebuild an import run from a register row."""
    return ImportRun(
        run_id=int(row["id"]),
        content_hash=str(row["content_hash"]),
        profile=str(row["profile"]),
        kind=str(row["kind"]),
        source=str(row["source"]),
        imported_at=dt.datetime.fromisoformat(str(row["imported_at"])),
        accepted=int(row["accepted"]),
        rejected=int(row["rejected"]),
    )


class ImportLedger:
    """Every file that has been through the front door."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def find_by_hash(self, content_hash: str) -> ImportRun | None:
        """The run that loaded these exact bytes, if there was one."""
        row = self.database.query_one(
            "SELECT id, content_hash, profile, kind, source, imported_at, accepted, rejected"
            " FROM import_run WHERE content_hash = ?",
            (content_hash,),
        )
        return None if row is None else row_to_run(row)

    def already_seen(self, content_hash: str) -> bool:
        """Whether these bytes have been through before."""
        return self.find_by_hash(content_hash) is not None

    def record(
        self,
        result: ReadResult,
        *,
        kind: str,
        now: dt.datetime,
    ) -> ImportRun:
        """Write a run and its quarantine, refusing a file already loaded."""
        existing = self.find_by_hash(result.content_hash)
        if existing is not None:
            raise ConflictError(
                "this file has been loaded before",
                content_hash=result.content_hash,
                run_id=existing.run_id,
                source=existing.source,
                imported_at=existing.imported_at.isoformat(),
            )
        cursor = self.database.execute(
            "INSERT INTO import_run (content_hash, profile, kind, source, imported_at,"
            " accepted, rejected) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.content_hash,
                result.profile_name,
                kind,
                result.source,
                now.isoformat(timespec="seconds"),
                result.accepted,
                result.rejected,
            ),
        )
        run_id = int(cursor.lastrowid or 0)
        rows = [
            (
                run_id,
                item.row_number,
                json.dumps(list(item.raw)),
                json.dumps(
                    [
                        {"field": error.field_name, "message": error.message, "raw": error.raw}
                        for error in item.errors
                    ]
                ),
            )
            for item in result.quarantine
        ]
        if rows:
            self.database.executemany(
                "INSERT INTO import_quarantine (run_id, row_number, raw, reasons)"
                " VALUES (?, ?, ?, ?)",
                rows,
            )
        return ImportRun(
            run_id=run_id,
            content_hash=result.content_hash,
            profile=result.profile_name,
            kind=kind,
            source=result.source,
            imported_at=now,
            accepted=result.accepted,
            rejected=result.rejected,
        )

    def get(self, run_id: int) -> ImportRun:
        """One run by its number."""
        row = self.database.query_one(
            "SELECT id, content_hash, profile, kind, source, imported_at, accepted, rejected"
            " FROM import_run WHERE id = ?",
            (run_id,),
        )
        if row is None:
            raise NotFoundError("no import run with that number", run_id=run_id)
        return row_to_run(row)

    def recent(self, limit: int = 20, *, kind: str | None = None) -> list[ImportRun]:
        """The most recent runs, newest first."""
        sql = (
            "SELECT id, content_hash, profile, kind, source, imported_at, accepted, rejected"
            " FROM import_run"
        )
        params: list[object] = []
        if kind is not None:
            sql += " WHERE kind = ?"
            params.append(kind)
        sql += " ORDER BY imported_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return [row_to_run(row) for row in self.database.query(sql, params)]

    def quarantine_for(self, run_id: int) -> list[QuarantinedRow]:
        """The rows one run could not read, in the shape the reader produced."""
        rows = self.database.query(
            "SELECT row_number, raw, reasons FROM import_quarantine"
            " WHERE run_id = ? ORDER BY row_number",
            (run_id,),
        )
        held: list[QuarantinedRow] = []
        for row in rows:
            reasons = json.loads(str(row["reasons"]))
            held.append(
                QuarantinedRow(
                    row_number=int(row["row_number"]),
                    raw=tuple(json.loads(str(row["raw"]))),
                    errors=tuple(
                        RowError(
                            field_name=str(item["field"]),
                            message=str(item["message"]),
                            raw=str(item["raw"]),
                        )
                        for item in reasons
                    ),
                )
            )
        return held

    def count(self) -> int:
        """How many files have been loaded."""
        return int(self.database.scalar("SELECT count(*) FROM import_run") or 0)
