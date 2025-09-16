"""Reading and writing potentials.

One visit to one lead on one day is one row, and the register refuses a second
one. A crew that reads the same post twice in a day has either fixed a bad
reading or written the wrong post number down, and both of those are worth
stopping on rather than averaging over.

Dates are stored as ISO text. SQLite sorts that lexicographically, which for
ISO dates is the same as sorting chronologically, so range queries work without
a date type.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterable

from dropcell.electrodes import Electrode
from dropcell.model.enums import LeadKind
from dropcell.model.ids import normalise_code
from dropcell.model.reading import Reading
from dropcell.store.database import Database

READING_COLUMNS = (
    "test_point_code, lead, taken_on, on_mv, off_mv, native_mv, "
    "electrode, cell_serial, technician, comment"
)


def row_to_reading(row: sqlite3.Row) -> Reading:
    """Rebuild a reading from a register row."""
    return Reading(
        test_point_code=str(row["test_point_code"]),
        lead=LeadKind(row["lead"]),
        taken_on=dt.date.fromisoformat(str(row["taken_on"])),
        on_mv=float(row["on_mv"]),
        off_mv=None if row["off_mv"] is None else float(row["off_mv"]),
        native_mv=None if row["native_mv"] is None else float(row["native_mv"]),
        electrode=Electrode(row["electrode"]),
        cell_serial=str(row["cell_serial"]),
        technician=str(row["technician"]),
        comment=str(row["comment"]),
    )


def _values(reading: Reading) -> tuple[object, ...]:
    return (
        reading.test_point_code,
        str(reading.lead),
        reading.taken_on.isoformat(),
        reading.on_mv,
        reading.off_mv,
        reading.native_mv,
        str(reading.electrode),
        reading.cell_serial,
        reading.technician,
        reading.comment,
    )


class ReadingRepository:
    """Every potential in the register."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, reading: Reading) -> Reading:
        """Insert one reading."""
        self.database.execute(
            f"INSERT INTO reading ({READING_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _values(reading),
        )
        return reading

    def add_many(self, readings: Iterable[Reading]) -> int:
        """Insert a batch of readings and report how many landed."""
        rows = [_values(reading) for reading in readings]
        if not rows:
            return 0
        self.database.executemany(
            f"INSERT INTO reading ({READING_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        return len(rows)

    def for_point(
        self,
        code: str,
        *,
        lead: LeadKind | None = None,
        since: dt.date | None = None,
        until: dt.date | None = None,
    ) -> list[Reading]:
        """Readings at one post, oldest first, narrowed by lead and by date."""
        sql = f"SELECT {READING_COLUMNS} FROM reading WHERE test_point_code = ?"
        params: list[object] = [normalise_code(code, kind="test point code")]
        if lead is not None:
            sql += " AND lead = ?"
            params.append(str(lead))
        if since is not None:
            sql += " AND taken_on >= ?"
            params.append(since.isoformat())
        if until is not None:
            sql += " AND taken_on <= ?"
            params.append(until.isoformat())
        sql += " ORDER BY taken_on, lead"
        return [row_to_reading(row) for row in self.database.query(sql, params)]

    def latest_for_point(self, code: str, lead: LeadKind) -> Reading | None:
        """The most recent reading off one lead at one post."""
        row = self.database.query_one(
            f"SELECT {READING_COLUMNS} FROM reading"
            " WHERE test_point_code = ? AND lead = ? ORDER BY taken_on DESC LIMIT 1",
            (normalise_code(code, kind="test point code"), str(lead)),
        )
        return None if row is None else row_to_reading(row)

    def for_line(
        self,
        line_code: str,
        *,
        lead: LeadKind | None = None,
        since: dt.date | None = None,
        until: dt.date | None = None,
    ) -> list[Reading]:
        """Every reading on a line, in stationing order and then by date."""
        sql = (
            "SELECT r.test_point_code AS test_point_code, r.lead AS lead,"
            " r.taken_on AS taken_on, r.on_mv AS on_mv, r.off_mv AS off_mv,"
            " r.native_mv AS native_mv, r.electrode AS electrode,"
            " r.cell_serial AS cell_serial, r.technician AS technician,"
            " r.comment AS comment"
            " FROM reading r JOIN test_point t ON t.code = r.test_point_code"
            " WHERE t.line_code = ?"
        )
        params: list[object] = [normalise_code(line_code, kind="line code")]
        if lead is not None:
            sql += " AND r.lead = ?"
            params.append(str(lead))
        if since is not None:
            sql += " AND r.taken_on >= ?"
            params.append(since.isoformat())
        if until is not None:
            sql += " AND r.taken_on <= ?"
            params.append(until.isoformat())
        sql += " ORDER BY t.station_m, r.taken_on"
        return [row_to_reading(row) for row in self.database.query(sql, params)]

    def latest_per_point(
        self, line_code: str, lead: LeadKind, *, until: dt.date | None = None
    ) -> dict[str, Reading]:
        """The most recent reading off one lead at every post on a line.

        One query rather than one per post. A line with four hundred posts was
        costing four hundred round trips to build a report that reads every one
        of them, and the join here does the same work in a single pass.

        A cutoff date is not a filter for convenience. A report headed "as at"
        a date that judges a post on a reading taken after it is not a report of
        that date, and last year's annual document is exactly the case where
        readings from after the year end exist.
        """
        cutoff = "" if until is None else " AND r.taken_on <= :until"
        inner = "" if until is None else " AND taken_on <= :until"
        parameters: dict[str, object] = {
            "line_code": normalise_code(line_code, kind="line code"),
            "lead": str(lead),
        }
        if until is not None:
            parameters["until"] = until.isoformat()
        rows = self.database.query(
            "SELECT r.test_point_code AS test_point_code, r.lead AS lead,"
            " r.taken_on AS taken_on, r.on_mv AS on_mv, r.off_mv AS off_mv,"
            " r.native_mv AS native_mv, r.electrode AS electrode,"
            " r.cell_serial AS cell_serial, r.technician AS technician,"
            " r.comment AS comment"
            " FROM reading r JOIN test_point t ON t.code = r.test_point_code"
            " WHERE t.line_code = :line_code AND r.lead = :lead"
            + cutoff
            + " AND r.taken_on = ("
            "   SELECT max(taken_on) FROM reading"
            "   WHERE test_point_code = r.test_point_code AND lead = r.lead" + inner + " )",
            parameters,
        )
        return {str(row["test_point_code"]): row_to_reading(row) for row in rows}

    def last_read_on(self, code: str, lead: LeadKind) -> dt.date | None:
        """When a lead was last visited, which is what the schedule runs off."""
        latest = self.latest_for_point(code, lead)
        return None if latest is None else latest.taken_on

    def count(self) -> int:
        """How many readings the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM reading") or 0)

    def delete_for_point(self, code: str) -> int:
        """Drop every reading at one post and report how many went."""
        cursor = self.database.execute(
            "DELETE FROM reading WHERE test_point_code = ?",
            (normalise_code(code, kind="test point code"),),
        )
        return int(cursor.rowcount)
