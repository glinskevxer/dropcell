"""Reading and writing segments.

A segment is stored as two numbers rather than as a range, because SQLite has
no range type and because half the useful questions about segments are
comparisons on those two numbers. Which segment covers this station, which two
segments overlap, which segments does this survey run across.
"""

from __future__ import annotations

import sqlite3

from dropcell.errors import ConflictError, NotFoundError
from dropcell.model.enums import ClassLocation, CoatingType, ProtectionMethod
from dropcell.model.ids import normalise_code
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database

SEGMENT_COLUMNS = (
    "code, line_code, start_m, end_m, coating, protection, class_location, "
    "outside_diameter_mm, wall_thickness_mm, installed_year, depth_of_cover_m, "
    "soil_resistivity_ohm_m, notes"
)

_PLACEHOLDERS = ", ".join("?" * 13)


def row_to_segment(row: sqlite3.Row) -> Segment:
    """Rebuild a segment from a register row."""
    resistivity = row["soil_resistivity_ohm_m"]
    return Segment(
        code=str(row["code"]),
        line_code=str(row["line_code"]),
        extent=StationRange(Station(float(row["start_m"])), Station(float(row["end_m"]))),
        coating=CoatingType(row["coating"]),
        protection=ProtectionMethod(row["protection"]),
        class_location=ClassLocation(int(row["class_location"])),
        outside_diameter_mm=float(row["outside_diameter_mm"]),
        wall_thickness_mm=float(row["wall_thickness_mm"]),
        installed_year=int(row["installed_year"]),
        depth_of_cover_m=float(row["depth_of_cover_m"]),
        soil_resistivity_ohm_m=None if resistivity is None else float(resistivity),
        notes=str(row["notes"]),
    )


def _values(segment: Segment) -> tuple[object, ...]:
    return (
        segment.code,
        segment.line_code,
        segment.extent.start.metres,
        segment.extent.end.metres,
        str(segment.coating),
        str(segment.protection),
        int(segment.class_location),
        segment.outside_diameter_mm,
        segment.wall_thickness_mm,
        segment.installed_year,
        segment.depth_of_cover_m,
        segment.soil_resistivity_ohm_m,
        segment.notes,
    )


class SegmentRepository:
    """Every segment in the register."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, segment: Segment, *, allow_overlap: bool = False) -> Segment:
        """Insert a segment, refusing one that lies on top of another by default.

        Overlapping segments are usually a data entry mistake, and they make a
        criterion ambiguous at every station both of them cover. They are still
        allowed under a flag, because a real line does get resegmented in stages
        and there is a window where both descriptions exist.
        """
        if not allow_overlap:
            clash = self.overlapping(segment)
            if clash:
                raise ConflictError(
                    "segment overlaps one already stored",
                    code=segment.code,
                    clashes_with=[item.code for item in clash],
                )
        self.database.execute(
            f"INSERT INTO segment ({SEGMENT_COLUMNS}) VALUES ({_PLACEHOLDERS})",
            _values(segment),
        )
        return segment

    def find(self, code: str) -> Segment | None:
        """The segment under that code, or nothing."""
        row = self.database.query_one(
            f"SELECT {SEGMENT_COLUMNS} FROM segment WHERE code = ?",
            (normalise_code(code, kind="segment code"),),
        )
        return None if row is None else row_to_segment(row)

    def get(self, code: str) -> Segment:
        """The segment under that code, or a refusal naming it."""
        segment = self.find(code)
        if segment is None:
            raise NotFoundError("no segment with that code", code=code)
        return segment

    def for_line(self, line_code: str) -> list[Segment]:
        """Every segment of one line, in stationing order."""
        rows = self.database.query(
            f"SELECT {SEGMENT_COLUMNS} FROM segment WHERE line_code = ? ORDER BY start_m",
            (normalise_code(line_code, kind="line code"),),
        )
        return [row_to_segment(row) for row in rows]

    def covering(self, line_code: str, station: Station) -> list[Segment]:
        """Every segment of that line which covers the station."""
        rows = self.database.query(
            f"SELECT {SEGMENT_COLUMNS} FROM segment"
            " WHERE line_code = ? AND start_m <= ? AND end_m >= ? ORDER BY start_m",
            (normalise_code(line_code, kind="line code"), station.metres, station.metres),
        )
        return [row_to_segment(row) for row in rows]

    def overlapping(self, segment: Segment) -> list[Segment]:
        """Every stored segment of the same line that shares pipe with this one."""
        rows = self.database.query(
            f"SELECT {SEGMENT_COLUMNS} FROM segment"
            " WHERE line_code = ? AND code <> ? AND start_m <= ? AND end_m >= ?"
            " ORDER BY start_m",
            (
                segment.line_code,
                segment.code,
                segment.extent.end.metres,
                segment.extent.start.metres,
            ),
        )
        return [row_to_segment(row) for row in rows]

    def all(self) -> list[Segment]:
        """Every segment, line by line and then in stationing order."""
        rows = self.database.query(
            f"SELECT {SEGMENT_COLUMNS} FROM segment ORDER BY line_code, start_m"
        )
        return [row_to_segment(row) for row in rows]

    def count(self) -> int:
        """How many segments the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM segment") or 0)

    def delete(self, code: str) -> None:
        """Remove a segment."""
        normalised = normalise_code(code, kind="segment code")
        cursor = self.database.execute("DELETE FROM segment WHERE code = ?", (normalised,))
        if cursor.rowcount == 0:
            raise NotFoundError("no segment with that code", code=normalised)
