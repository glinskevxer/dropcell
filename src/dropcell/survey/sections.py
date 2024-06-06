"""Turning a close interval trace into stretches somebody can be sent to dig.

A profile of forty thousand readings is not a work list. What comes off it is a
handful of sections, each one a run of pipe that failed the criterion, and each
one with a length and a worst reading attached. Everything hard about doing that
is in the edges.

A single reading under criterion has no length at all, and reporting a zero
metre finding is worse than useless. Each reading stands for the half interval
either side of it, so a lone point becomes one interval of pipe.

Two failing runs separated by four good readings are usually one problem seen
through a bit of noise, and separated by four hundred good readings they are
two. The tolerance that decides which is a judgement, so the caller sets it.

A step with no off reading is not a passing reading. Treating it as one closes
a section that should have stayed open, and treating it as a failure invents
pipe that was never measured. It breaks the run and belongs to neither side.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dropcell.criteria.potential import DEFAULT_PROTECTION_MV
from dropcell.errors import ValidationError
from dropcell.stationing import Station, StationRange
from dropcell.survey.cis import CisPoint, CisSurvey

MINOR_SHORTFALL_MV = 25.0
SEVERE_SHORTFALL_MV = 75.0


class Severity(StrEnum):
    """How badly a section misses the criterion."""

    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"

    @property
    def rank(self) -> int:
        """An order to sort by, worst first when reversed."""
        return {"minor": 1, "moderate": 2, "severe": 3}[self.value]


def classify_shortfall(shortfall_mv: float) -> Severity:
    """Put a shortfall in the band a work list is prioritised by."""
    if shortfall_mv < 0:
        raise ValidationError("a shortfall is a positive number", shortfall_mv=shortfall_mv)
    if shortfall_mv >= SEVERE_SHORTFALL_MV:
        return Severity.SEVERE
    if shortfall_mv >= MINOR_SHORTFALL_MV:
        return Severity.MODERATE
    return Severity.MINOR


@dataclass(frozen=True)
class UnderCriterionSection:
    """A run of pipe that failed the criterion."""

    extent: StationRange
    readings: int
    worst_off_mv: float
    mean_off_mv: float
    threshold_mv: float

    @property
    def length_m(self) -> float:
        """How much pipe the section covers."""
        return self.extent.length_m

    @property
    def worst_shortfall_mv(self) -> float:
        """How far the worst reading fell short of the criterion."""
        return self.worst_off_mv - self.threshold_mv

    @property
    def mean_shortfall_mv(self) -> float:
        """How far the section fell short on average."""
        return self.mean_off_mv - self.threshold_mv

    @property
    def severity(self) -> Severity:
        """The band this section is prioritised in."""
        return classify_shortfall(self.worst_shortfall_mv)


def _summarise(run: list[CisPoint], threshold_mv: float, pad_m: float) -> UnderCriterionSection:
    values = [point.off_mv for point in run if point.off_mv is not None]
    start = run[0].station.metres - pad_m
    end = run[-1].station.metres + pad_m
    return UnderCriterionSection(
        extent=StationRange(Station(start), Station(end)),
        readings=len(run),
        worst_off_mv=max(values),
        mean_off_mv=sum(values) / len(values),
        threshold_mv=threshold_mv,
    )


def find_under_criterion(
    survey: CisSurvey,
    *,
    threshold_mv: float = DEFAULT_PROTECTION_MV,
    gap_tolerance_m: float = 0.0,
    minimum_length_m: float = 0.0,
) -> list[UnderCriterionSection]:
    """Pull the failing stretches out of one close interval survey."""
    if gap_tolerance_m < 0:
        raise ValidationError("gap tolerance cannot be negative", value=gap_tolerance_m)
    if minimum_length_m < 0:
        raise ValidationError("minimum length cannot be negative", value=minimum_length_m)
    pad = survey.nominal_interval_m / 2.0
    runs: list[list[CisPoint]] = []
    current: list[CisPoint] = []
    for step in survey.points:
        failing = step.off_mv is not None and step.off_mv > threshold_mv
        if failing:
            current.append(step)
            continue
        if current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    sections = [_summarise(run, threshold_mv, pad) for run in runs]
    joined = _join(sections, gap_tolerance_m, threshold_mv)
    return [section for section in joined if section.length_m >= minimum_length_m]


def _join(
    sections: list[UnderCriterionSection],
    gap_tolerance_m: float,
    threshold_mv: float,
) -> list[UnderCriterionSection]:
    if gap_tolerance_m <= 0 or len(sections) < 2:
        return sections
    joined: list[UnderCriterionSection] = []
    for section in sections:
        if not joined:
            joined.append(section)
            continue
        previous = joined[-1]
        if section.extent.start.metres - previous.extent.end.metres <= gap_tolerance_m:
            readings = previous.readings + section.readings
            joined[-1] = UnderCriterionSection(
                extent=StationRange(previous.extent.start, section.extent.end),
                readings=readings,
                worst_off_mv=max(previous.worst_off_mv, section.worst_off_mv),
                mean_off_mv=(
                    previous.mean_off_mv * previous.readings
                    + section.mean_off_mv * section.readings
                )
                / readings,
                threshold_mv=threshold_mv,
            )
            continue
        joined.append(section)
    return joined


def total_under_criterion_m(sections: list[UnderCriterionSection]) -> float:
    """How much pipe the sections cover in total."""
    return sum(section.length_m for section in sections)


def worst_section(sections: list[UnderCriterionSection]) -> UnderCriterionSection | None:
    """The section with the worst single reading in it."""
    if not sections:
        return None
    return max(sections, key=lambda section: section.worst_off_mv)
