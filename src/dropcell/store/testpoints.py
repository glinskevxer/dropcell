"""Reading and writing test posts.

The lead set is stored as a sorted comma separated string. It is a small closed
vocabulary, it is never queried by element in anger, and a join table for four
values on a few thousand posts costs more to read than it saves. Sorting it on
the way in means the same post always serialises the same way, which keeps
imports idempotent.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.ids import normalise_code
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station, StationRange
from dropcell.store.base import Repository

TEST_POINT_COLUMNS = (
    "code, line_code, station_m, leads, installed_on, description, permanent_reference_cell"
)


def encode_leads(leads: frozenset[LeadKind]) -> str:
    """Serialise a lead set so the same post always writes the same string."""
    return ",".join(sorted(str(lead) for lead in leads))


def decode_leads(raw: str) -> frozenset[LeadKind]:
    """Read a lead set back, refusing a value this build does not know."""
    if not raw.strip():
        raise ValidationError("stored test point has no leads")
    try:
        return frozenset(LeadKind(part) for part in raw.split(","))
    except ValueError as exc:
        raise ValidationError("stored lead kind is not one this build knows", raw=raw) from exc


def row_to_test_point(row: sqlite3.Row) -> TestPoint:
    """Rebuild a test post from a register row."""
    return TestPoint(
        code=str(row["code"]),
        line_code=str(row["line_code"]),
        station=Station(float(row["station_m"])),
        leads=decode_leads(str(row["leads"])),
        installed_on=dt.date.fromisoformat(str(row["installed_on"])),
        description=str(row["description"]),
        permanent_reference_cell=bool(row["permanent_reference_cell"]),
    )


class TestPointRepository(Repository[TestPoint]):
    """Every post in the register."""

    table = "test_point"
    columns = TEST_POINT_COLUMNS
    noun = "test point"
    order_by = "line_code, station_m"

    def to_record(self, row: sqlite3.Row) -> TestPoint:
        """Rebuild a test post from a register row."""
        return row_to_test_point(row)

    def add(self, post: TestPoint) -> TestPoint:
        """Insert a post."""
        self.database.execute(
            f"INSERT INTO test_point ({TEST_POINT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                post.code,
                post.line_code,
                post.station.metres,
                encode_leads(post.leads),
                post.installed_on.isoformat(),
                post.description,
                int(post.permanent_reference_cell),
            ),
        )
        return post

    def for_line(self, line_code: str) -> list[TestPoint]:
        """Every post on one line, in stationing order."""
        rows = self.database.query(
            f"SELECT {TEST_POINT_COLUMNS} FROM test_point WHERE line_code = ?"
            " ORDER BY station_m, code",
            (normalise_code(line_code, kind="line code"),),
        )
        return [row_to_test_point(row) for row in rows]

    def in_range(self, line_code: str, extent: StationRange) -> list[TestPoint]:
        """Every post of one line that falls inside a stretch of it."""
        rows = self.database.query(
            f"SELECT {TEST_POINT_COLUMNS} FROM test_point"
            " WHERE line_code = ? AND station_m BETWEEN ? AND ? ORDER BY station_m, code",
            (
                normalise_code(line_code, kind="line code"),
                extent.start.metres,
                extent.end.metres,
            ),
        )
        return [row_to_test_point(row) for row in rows]

    def with_lead(self, line_code: str, lead: LeadKind) -> list[TestPoint]:
        """Every post on one line that carries a particular lead."""
        return [post for post in self.for_line(line_code) if post.has(lead)]
