"""Reading and writing lines.

The repositories are deliberately dull. They turn a row into a record and a
record into a row, and they raise the package's own errors rather than SQLite's.
No repository decides anything: a rule that belongs to the domain lives on the
record or in an engine, never in a SELECT.
"""

from __future__ import annotations

import sqlite3

from dropcell.errors import NotFoundError
from dropcell.model.enums import Commodity
from dropcell.model.ids import normalise_code
from dropcell.model.line import Line
from dropcell.stationing import Convention
from dropcell.store.database import Database

LINE_COLUMNS = (
    "code, name, operator, commodity, length_m, nominal_diameter_mm, "
    "installed_year, convention, notes"
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
        notes=str(row["notes"]),
    )


class LineRepository:
    """Every line in the register."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, line: Line) -> Line:
        """Insert a line, refusing a code that is already taken."""
        self.database.execute(
            f"INSERT INTO line ({LINE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                line.code,
                line.name,
                line.operator,
                str(line.commodity),
                line.length_m,
                line.nominal_diameter_mm,
                line.installed_year,
                str(line.convention),
                line.notes,
            ),
        )
        return line

    def save(self, line: Line) -> Line:
        """Insert a line or replace the one already stored under its code."""
        self.database.execute(
            f"INSERT INTO line ({LINE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (code) DO UPDATE SET"
            " name = excluded.name, operator = excluded.operator,"
            " commodity = excluded.commodity, length_m = excluded.length_m,"
            " nominal_diameter_mm = excluded.nominal_diameter_mm,"
            " installed_year = excluded.installed_year,"
            " convention = excluded.convention, notes = excluded.notes",
            (
                line.code,
                line.name,
                line.operator,
                str(line.commodity),
                line.length_m,
                line.nominal_diameter_mm,
                line.installed_year,
                str(line.convention),
                line.notes,
            ),
        )
        return line

    def find(self, code: str) -> Line | None:
        """The line under that code, or nothing."""
        row = self.database.query_one(
            f"SELECT {LINE_COLUMNS} FROM line WHERE code = ?",
            (normalise_code(code, kind="line code"),),
        )
        return None if row is None else row_to_line(row)

    def get(self, code: str) -> Line:
        """The line under that code, or a refusal naming it."""
        line = self.find(code)
        if line is None:
            raise NotFoundError("no line with that code", code=code)
        return line

    def all(self) -> list[Line]:
        """Every line, in code order."""
        rows = self.database.query(f"SELECT {LINE_COLUMNS} FROM line ORDER BY code")
        return [row_to_line(row) for row in rows]

    def count(self) -> int:
        """How many lines the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM line") or 0)

    def delete(self, code: str) -> None:
        """Remove a line and everything hanging off it."""
        normalised = normalise_code(code, kind="line code")
        cursor = self.database.execute("DELETE FROM line WHERE code = ?", (normalised,))
        if cursor.rowcount == 0:
            raise NotFoundError("no line with that code", code=normalised)
