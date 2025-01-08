"""Backing the register up, and checking it is not quietly damaged.

A register is one file on somebody's laptop and it holds twenty years of field
work. Copying it while a write is in flight produces a file that opens, queries
and is missing the last transaction, which is the failure mode worth designing
against because it looks like success.

SQLite's own backup API copies a live database consistently. It is used here in
preference to anything that treats the file as bytes, and the destination is
written to a temporary name and moved into place, so an interrupted backup
leaves the previous one standing rather than half of a new one.

Vacuum is separate and is not maintenance in the sense of being routine. It
rewrites the whole file, it needs as much free space again, and on a register
that is mostly appended to it buys very little. It is here because deleting a
line with twenty years of readings on it leaves a great deal of free space, and
that is the one time it is worth doing.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from dropcell.errors import StoreError
from dropcell.store.database import Database


@dataclass(frozen=True)
class RegisterStats:
    """What is in the register, by row count."""

    tables: dict[str, int]
    page_count: int
    page_size: int
    free_pages: int

    @property
    def size_bytes(self) -> int:
        """How big the file is."""
        return self.page_count * self.page_size

    @property
    def free_bytes(self) -> int:
        """How much of that is space nothing is using."""
        return self.free_pages * self.page_size

    @property
    def free_share(self) -> float:
        """The share of the file that is free space."""
        return 0.0 if self.page_count == 0 else self.free_pages / self.page_count

    @property
    def rows(self) -> int:
        """How many rows the register holds in total."""
        return sum(self.tables.values())

    @property
    def worth_vacuuming(self) -> bool:
        """Whether enough of the file is free space to be worth rewriting it."""
        return self.free_share > 0.25 and self.free_bytes > 1_000_000


def table_names(database: Database) -> list[str]:
    """Every table in the register, leaving SQLite's own alone."""
    rows = database.query(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [str(row["name"]) for row in rows]


def stats(database: Database) -> RegisterStats:
    """Count what the register holds and how much room it is taking."""
    counts: dict[str, int] = {}
    for name in table_names(database):
        counts[name] = int(database.scalar(f"SELECT count(*) FROM {name}") or 0)
    return RegisterStats(
        tables=counts,
        page_count=int(database.scalar("PRAGMA page_count") or 0),
        page_size=int(database.scalar("PRAGMA page_size") or 0),
        free_pages=int(database.scalar("PRAGMA freelist_count") or 0),
    )


def integrity(database: Database) -> list[str]:
    """Whatever SQLite says about the file, or nothing if it is sound."""
    rows = database.query("PRAGMA integrity_check")
    said = [str(row[0]) for row in rows]
    return [] if said == ["ok"] else said


def foreign_key_violations(database: Database) -> list[str]:
    """Rows pointing at parents that are not there."""
    rows = database.query("PRAGMA foreign_key_check")
    return [f"{row[0]} row {row[1]} references {row[2]}" for row in rows]


def backup(database: Database, destination: Path | str) -> Path:
    """Copy a live register consistently, leaving the old copy if it fails."""
    target = Path(destination)
    if target.exists() and target.is_dir():
        raise StoreError("the backup destination is a directory", path=str(target))
    staging = target.with_name(target.name + ".part")
    try:
        with sqlite3.connect(str(staging)) as handle:
            database.connection.backup(handle)
    except sqlite3.Error as exc:
        staging.unlink(missing_ok=True)
        raise StoreError("the backup failed", path=str(target), reason=str(exc)) from exc
    except OSError as exc:
        raise StoreError("cannot write the backup", path=str(target)) from exc
    shutil.move(str(staging), str(target))
    return target


def vacuum(database: Database) -> int:
    """Rewrite the file and report how many bytes came back."""
    before = stats(database)
    database.execute("VACUUM")
    after = stats(database)
    return before.size_bytes - after.size_bytes
