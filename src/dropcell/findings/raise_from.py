"""Turning survey output into findings somebody owns.

Each analysis module produces its own shape: a close interval survey gives
sections, a gradient survey gives indications, a casing test gives a status.
None of those is a work item. This is where they become one, and the conversion
is doing three things that are easy to get wrong separately.

It gives the finding a code, and the codes have to be unique and to keep
running from whatever is already in the register rather than restarting at one
every time a survey is imported.

It gives the finding a date by which something has to happen, and that date
comes from the severity the analysis worked out rather than from a default. A
severe section and a hairline one both landing on the same date is the same as
having no dates at all.

And it keeps the source. A finding whose provenance is lost is a finding
nobody can check, and the first question asked about every one of these is
which survey it came off.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable

from dropcell.errors import ValidationError
from dropcell.findings.finding import Finding, FindingKind
from dropcell.interference.casing import CasingAssessment, CasingStatus
from dropcell.stationing import Station, StationRange
from dropcell.survey.dcvg import DcvgIndication
from dropcell.survey.sections import Severity, UnderCriterionSection

CODE_PATTERN = re.compile(r"^F-(\d{4})-(\d+)$")

SECTION_RESPONSE_DAYS: dict[Severity, int] = {
    Severity.SEVERE: 90,
    Severity.MODERATE: 180,
    Severity.MINOR: 365,
}


def next_sequence(existing: Iterable[str], year: int) -> int:
    """The next free sequence number for a year, given what is already stored."""
    highest = 0
    for code in existing:
        match = CODE_PATTERN.match(code)
        if match is None or int(match.group(1)) != year:
            continue
        highest = max(highest, int(match.group(2)))
    return highest + 1


def format_code(year: int, sequence: int) -> str:
    """Build a finding code from a year and a sequence number."""
    if sequence < 1:
        raise ValidationError("finding sequence numbers start at one", sequence=sequence)
    return f"F-{year:04d}-{sequence:03d}"


def from_cis_sections(
    sections: list[UnderCriterionSection],
    *,
    line_code: str,
    raised_on: dt.date,
    source: str,
    existing_codes: Iterable[str] = (),
) -> list[Finding]:
    """One finding per stretch of pipe that failed the criterion."""
    sequence = next_sequence(existing_codes, raised_on.year)
    made: list[Finding] = []
    for section in sections:
        days = SECTION_RESPONSE_DAYS[section.severity]
        made.append(
            Finding(
                code=format_code(raised_on.year, sequence),
                line_code=line_code,
                kind=FindingKind.UNDER_CRITERION,
                raised_on=raised_on,
                extent=section.extent,
                summary=(
                    f"{section.length_m:.0f} m under criterion, worst reading "
                    f"{section.worst_off_mv:.0f} mV, {section.severity}"
                ),
                due_by=raised_on + dt.timedelta(days=days),
                source=source,
            )
        )
        sequence += 1
    return made


def from_dcvg(
    indications: list[DcvgIndication],
    *,
    raised_on: dt.date,
    source: str,
    defect_length_m: float = 1.0,
    existing_codes: Iterable[str] = (),
) -> list[Finding]:
    """One finding per coating defect a gradient survey turned up."""
    if defect_length_m <= 0:
        raise ValidationError("a defect has to be given some length", value=defect_length_m)
    sequence = next_sequence(existing_codes, raised_on.year)
    made: list[Finding] = []
    for indication in indications:
        start = indication.station
        end = Station(start.metres + defect_length_m)
        kind = FindingKind.INTERFERENCE if indication.anodic else FindingKind.COATING_DEFECT
        made.append(
            Finding(
                code=format_code(raised_on.year, sequence),
                line_code=indication.line_code,
                kind=kind,
                raised_on=raised_on,
                extent=StationRange(start, end),
                summary=(
                    f"category {int(indication.category)} indication at "
                    f"{indication.percent_ir:.0f} percent IR"
                    + (", current leaving the pipe" if indication.anodic else "")
                ),
                due_by=indication.due_by,
                source=source,
            )
        )
        sequence += 1
    return made


def from_casing(
    assessments: list[CasingAssessment],
    *,
    line_code: str,
    stations: dict[str, Station],
    source: str,
    casing_length_m: float = 20.0,
    existing_codes: Iterable[str] = (),
) -> list[Finding]:
    """One finding per crossing whose casing is not clear."""
    sequence = 0
    made: list[Finding] = []
    for assessment in assessments:
        if (
            not assessment.status.needs_work
            and assessment.status is not CasingStatus.INDETERMINATE
        ):
            continue
        station = stations.get(assessment.casing_code)
        if station is None:
            raise ValidationError(
                "no station is known for that casing",
                casing_code=assessment.casing_code,
            )
        if sequence == 0:
            sequence = next_sequence(existing_codes, assessment.tested_on.year)
        made.append(
            Finding(
                code=format_code(assessment.tested_on.year, sequence),
                line_code=line_code,
                kind=FindingKind.SHORTED_CASING,
                raised_on=assessment.tested_on,
                extent=StationRange(station, Station(station.metres + casing_length_m)),
                summary=(
                    f"{assessment.casing_code} reads {assessment.status}, "
                    f"{assessment.separation_mv:.0f} mV between pipe and casing"
                ),
                due_by=assessment.due_by,
                source=source,
            )
        )
        sequence += 1
    return made
