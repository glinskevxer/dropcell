"""Reading and writing segments.

A segment is stored as two numbers rather than as a range, because SQLite has
no range type and because half the useful questions about segments are
comparisons on those two numbers. Which segment covers this station, which two
segments overlap, which segments does this survey run across.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from dropcell.errors import ConflictError, ValidationError
from dropcell.model.enums import ClassLocation, CoatingType, ProtectionMethod
from dropcell.model.ids import normalise_code
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange
from dropcell.store.base import Repository

SEGMENT_COLUMNS = (
    "code, line_code, start_m, end_m, coating, protection, class_location, "
    "outside_diameter_mm, wall_thickness_mm, installed_year, depth_of_cover_m, "
    "soil_resistivity_ohm_m, notes"
)

_PLACEHOLDERS = ", ".join("?" * 13)

BOUNDARY_GAP_M = 0.01


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


class SegmentRepository(Repository[Segment]):
    """Every segment in the register."""

    table = "segment"
    columns = SEGMENT_COLUMNS
    noun = "segment"
    order_by = "line_code, start_m"

    def to_record(self, row: sqlite3.Row) -> Segment:
        """Rebuild a segment from a register row."""
        return row_to_segment(row)

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

    def split(
        self, code: str, at: Station, *, left_code: str = "", right_code: str = ""
    ) -> tuple[Segment, Segment]:
        """Cut one segment in two at a station.

        Resegmentation is not a rare event. A road widening puts a new casing
        in the middle of a segment, a housing estate moves the class location
        of half of it, a rehabilitation project recoats a mile. All of those
        turn one segment into two, and doing it by hand means deleting the
        original, which takes the history of everything that referred to it.

        The two halves inherit everything from the original except their codes
        and their extents, which is right: a split is a statement about where
        the boundary is, not about what changed. Whatever did change is set on
        one half afterwards.

        The boundary station belongs to the second half. Segments in this
        register are not allowed to share even one station, because a station
        two segments both cover has two coatings and two criteria, so the first
        half stops a centimetre short. That centimetre is smaller than any
        measurement on a pipeline and it keeps the rule exact.
        """
        original = self.get(code)
        if not original.extent.contains(at):
            raise ValidationError(
                "that station is not on this segment",
                code=original.code,
                station_m=at.metres,
            )
        if at.metres in (original.extent.start.metres, original.extent.end.metres):
            raise ValidationError(
                "splitting at an end produces a segment with no length",
                code=original.code,
            )
        left = dataclasses.replace(
            original,
            code=left_code or f"{original.code}-A",
            extent=StationRange(original.extent.start, Station(at.metres - BOUNDARY_GAP_M)),
        )
        right = dataclasses.replace(
            original,
            code=right_code or f"{original.code}-B",
            extent=StationRange(at, original.extent.end),
        )
        if left.code == right.code:
            raise ValidationError("the two halves need different codes", code=original.code)
        with self.database.transaction():
            self.delete(original.code)
            self.add(left)
            self.add(right)
        return left, right
