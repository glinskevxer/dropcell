"""Moving one line between registers, which happens more than it should.

Lines change hands. A distribution network is sold, a transmission line is
transferred to a joint venture, a contractor holds a register for a client and
hands it back at the end of the term. What moves in every one of those cases is
one line and everything hanging off it, and what must not move is any of the
other lines in the same file.

So a transfer is a document rather than a copy of the register. It carries a
format version, because a document written today will be read by a build nobody
has written yet, and a document whose shape can only be guessed at is a document
that gets read wrongly rather than refused.

Nothing derived travels. Verdicts, rates and priorities are all worked out from
thresholds that the receiving register will have its own version of, and
shipping them would mean a line arriving with somebody else's criteria baked
into its history.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from dropcell.errors import ConflictError, ValidationError
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.enums import (
    ClassLocation,
    CoatingType,
    Commodity,
    LeadKind,
    LineStatus,
    ProtectionMethod,
)
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Convention, Station, StationRange
from dropcell.store.database import Database
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository

FORMAT = "dropcell-line-transfer"
FORMAT_VERSION = 1


def export_line(database: Database, code: str) -> dict[str, Any]:
    """Everything about one line, as a document."""
    line = LineRepository(database).get(code)
    segments = SegmentRepository(database).for_line(line.code)
    posts = TestPointRepository(database).for_line(line.code)
    readings = ReadingRepository(database)
    findings = FindingRepository(database).for_line(line.code)
    return {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "line": {
            "code": line.code,
            "name": line.name,
            "operator": line.operator,
            "commodity": str(line.commodity),
            "length_m": line.length_m,
            "nominal_diameter_mm": line.nominal_diameter_mm,
            "installed_year": line.installed_year,
            "convention": str(line.convention),
            "status": str(line.status),
            "retired_on": None if line.retired_on is None else line.retired_on.isoformat(),
            "notes": line.notes,
        },
        "segments": [
            {
                "code": segment.code,
                "start_m": segment.extent.start.metres,
                "end_m": segment.extent.end.metres,
                "coating": str(segment.coating),
                "protection": str(segment.protection),
                "class_location": int(segment.class_location),
                "outside_diameter_mm": segment.outside_diameter_mm,
                "wall_thickness_mm": segment.wall_thickness_mm,
                "installed_year": segment.installed_year,
                "depth_of_cover_m": segment.depth_of_cover_m,
                "soil_resistivity_ohm_m": segment.soil_resistivity_ohm_m,
                "notes": segment.notes,
            }
            for segment in segments
        ],
        "test_points": [
            {
                "code": post.code,
                "station_m": post.station.metres,
                "leads": sorted(str(lead) for lead in post.leads),
                "installed_on": post.installed_on.isoformat(),
                "description": post.description,
                "permanent_reference_cell": post.permanent_reference_cell,
            }
            for post in posts
        ],
        "readings": [
            {
                "test_point_code": reading.test_point_code,
                "lead": str(reading.lead),
                "taken_on": reading.taken_on.isoformat(),
                "on_mv": reading.on_cse_mv,
                "off_mv": reading.off_cse_mv,
                "native_mv": reading.native_mv,
                "cell_serial": reading.cell_serial,
                "technician": reading.technician,
                "comment": reading.comment,
            }
            for reading in readings.for_line(line.code)
        ],
        "findings": [
            {
                "code": finding.code,
                "kind": str(finding.kind),
                "raised_on": finding.raised_on.isoformat(),
                "start_m": finding.extent.start.metres,
                "end_m": finding.extent.end.metres,
                "summary": finding.summary,
                "state": str(finding.state),
                "due_by": None if finding.due_by is None else finding.due_by.isoformat(),
                "closed_on": (
                    None if finding.closed_on is None else finding.closed_on.isoformat()
                ),
                "closed_by": finding.closed_by,
                "closed_reason": finding.closed_reason,
                "source": finding.source,
            }
            for finding in findings
        ],
    }


def _date(value: Any) -> dt.date | None:
    return None if value is None else dt.date.fromisoformat(str(value))


def import_line(database: Database, payload: dict[str, Any]) -> Line:
    """Read a transfer document into a register that does not hold the line."""
    if payload.get("format") != FORMAT:
        raise ValidationError(
            "that is not a line transfer document", format=payload.get("format")
        )
    version = payload.get("version")
    if version != FORMAT_VERSION:
        raise ValidationError(
            "that document was written by a different build",
            version=version,
            expected=FORMAT_VERSION,
        )
    body = payload["line"]
    line = Line(
        code=str(body["code"]),
        name=str(body["name"]),
        operator=str(body["operator"]),
        commodity=Commodity(body["commodity"]),
        length_m=float(body["length_m"]),
        nominal_diameter_mm=float(body["nominal_diameter_mm"]),
        installed_year=int(body["installed_year"]),
        convention=Convention(body["convention"]),
        status=LineStatus(body.get("status", "in_service")),
        retired_on=_date(body.get("retired_on")),
        notes=str(body.get("notes", "")),
    )
    lines = LineRepository(database)
    if lines.exists(line.code):
        raise ConflictError("that line is already in this register", code=line.code)
    with database.transaction():
        lines.add(line)
        segments = SegmentRepository(database)
        for item in payload.get("segments", []):
            segments.add(
                Segment(
                    code=str(item["code"]),
                    line_code=line.code,
                    extent=StationRange(
                        Station(float(item["start_m"])), Station(float(item["end_m"]))
                    ),
                    coating=CoatingType(item["coating"]),
                    protection=ProtectionMethod(item["protection"]),
                    class_location=ClassLocation(int(item["class_location"])),
                    outside_diameter_mm=float(item["outside_diameter_mm"]),
                    wall_thickness_mm=float(item["wall_thickness_mm"]),
                    installed_year=int(item["installed_year"]),
                    depth_of_cover_m=float(item["depth_of_cover_m"]),
                    soil_resistivity_ohm_m=(
                        None
                        if item["soil_resistivity_ohm_m"] is None
                        else float(item["soil_resistivity_ohm_m"])
                    ),
                    notes=str(item.get("notes", "")),
                )
            )
        posts = TestPointRepository(database)
        for item in payload.get("test_points", []):
            posts.add(
                TestPoint(
                    code=str(item["code"]),
                    line_code=line.code,
                    station=Station(float(item["station_m"])),
                    leads=frozenset(LeadKind(lead) for lead in item["leads"]),
                    installed_on=dt.date.fromisoformat(str(item["installed_on"])),
                    description=str(item.get("description", "")),
                    permanent_reference_cell=bool(item.get("permanent_reference_cell")),
                )
            )
        readings = ReadingRepository(database)
        readings.add_many(
            Reading(
                test_point_code=str(item["test_point_code"]),
                lead=LeadKind(item["lead"]),
                taken_on=dt.date.fromisoformat(str(item["taken_on"])),
                on_mv=float(item["on_mv"]),
                off_mv=None if item["off_mv"] is None else float(item["off_mv"]),
                native_mv=None if item["native_mv"] is None else float(item["native_mv"]),
                cell_serial=str(item.get("cell_serial", "")),
                technician=str(item.get("technician", "")),
                comment=str(item.get("comment", "")),
            )
            for item in payload.get("readings", [])
        )
        findings = FindingRepository(database)
        for item in payload.get("findings", []):
            findings.raise_finding(
                Finding(
                    code=str(item["code"]),
                    line_code=line.code,
                    kind=FindingKind(item["kind"]),
                    raised_on=dt.date.fromisoformat(str(item["raised_on"])),
                    extent=StationRange(
                        Station(float(item["start_m"])), Station(float(item["end_m"]))
                    ),
                    summary=str(item["summary"]),
                    state=FindingState(item.get("state", "open")),
                    due_by=_date(item.get("due_by")),
                    closed_on=_date(item.get("closed_on")),
                    closed_by=str(item.get("closed_by", "")),
                    closed_reason=str(item.get("closed_reason", "")),
                    source=str(item.get("source", "")),
                ),
                actor="transfer",
            )
    return line
