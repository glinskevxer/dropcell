"""Reading and writing lines.

The repositories are deliberately dull. They turn a row into a record and a
record into a row, and they raise the package's own errors rather than SQLite's.
No repository decides anything: a rule that belongs to the domain lives on the
record or in an engine, never in a SELECT.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from dropcell.model.enums import Commodity, LineStatus
from dropcell.model.line import Line
from dropcell.stationing import Convention
from dropcell.store.base import Repository

LINE_COLUMNS = (
    "code, name, operator, commodity, length_m, nominal_diameter_mm, "
    "installed_year, convention, status, retired_on, notes"
)


def row_to_line(row: sqlite3.Row) -> Line:
    """Rebuild a line from a register row."""
    return Line(
        code=str(row["code"]),
        name=str(row["name"]),
        operator=str(row["operator"]),
        commodity=Commodity(row["commodity"]),
        length_m=float(row["length_m"]),
        nominal_diameter_mm=float(row["nominal_diameter_mm"]),
        installed_year=int(row["installed_year"]),
        convention=Convention(row["convention"]),
        status=LineStatus(row["status"]),
        retired_on=(
            None if row["retired_on"] is None else dt.date.fromisoformat(str(row["retired_on"]))
        ),
        notes=str(row["notes"]),
    )


def _values(line: Line) -> tuple[object, ...]:
    """One line in the order the columns are declared."""
    return (
        line.code,
        line.name,
        line.operator,
        str(line.commodity),
        line.length_m,
        line.nominal_diameter_mm,
        line.installed_year,
        str(line.convention),
        str(line.status),
        None if line.retired_on is None else line.retired_on.isoformat(),
        line.notes,
    )


class LineRepository(Repository[Line]):
    """Every line in the register."""

    table = "line"
    columns = LINE_COLUMNS
    noun = "line"

    def to_record(self, row: sqlite3.Row) -> Line:
        """Rebuild a line from a register row."""
        return row_to_line(row)

    def add(self, line: Line) -> Line:
        """Insert a line, refusing a code that is already taken."""
        self.database.execute(
            f"INSERT INTO line ({LINE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _values(line),
        )
        return line

    def save(self, line: Line) -> Line:
        """Insert a line or replace the one already stored under its code."""
        self.database.execute(
            f"INSERT INTO line ({LINE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (code) DO UPDATE SET"
            " name = excluded.name, operator = excluded.operator,"
            " commodity = excluded.commodity, length_m = excluded.length_m,"
            " nominal_diameter_mm = excluded.nominal_diameter_mm,"
            " installed_year = excluded.installed_year,"
            " convention = excluded.convention, status = excluded.status,"
            " retired_on = excluded.retired_on, notes = excluded.notes",
            _values(line),
        )
        return line

    def in_service(self) -> list[Line]:
        """Only the lines the monitoring rules still apply to."""
        return [line for line in self.all() if line.is_monitored]
