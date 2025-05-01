"""Ranking segments, which is a different question from ranking defects.

A dig list answers where to put an excavator this year. This answers where the
next survey, the next rectifier and the next set of test posts should go, and
those are decided on a stretch of pipe rather than on a point.

The terms are deliberately not the same as the dig score. A coating defect is
scored on what is known about it. A segment is scored on what is not: how long
since anybody looked, how much of it a post can see, whether the coating can
hide a problem from the survey at all. A segment with no findings against it is
either healthy or unwatched, and the whole point of this is to tell those apart.

Nothing here uses findings as a positive term. A stretch with twelve findings on
it is a stretch somebody has surveyed, and letting that raise its score sends
the next survey back to the piece of line everyone already understands.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.enums import ProtectionMethod, SoilCorrosivity
from dropcell.model.segment import Segment

AGE_TERM_PER_DECADE = 0.12
MAX_AGE_TERM = 2.5
UNSURVEYED_PER_YEAR = 0.25
MAX_STALENESS = 3.0
SHIELDING_TERM = 1.6
UNPROTECTED_TERM = 2.5
BLIND_TERM = 1.8

SOIL_TERM: dict[SoilCorrosivity, float] = {
    SoilCorrosivity.VERY_CORROSIVE: 1.8,
    SoilCorrosivity.CORROSIVE: 1.4,
    SoilCorrosivity.MODERATE: 1.15,
    SoilCorrosivity.MILD: 1.0,
    SoilCorrosivity.BENIGN: 0.85,
}
UNKNOWN_SOIL_TERM = 1.25


@dataclass(frozen=True)
class SegmentRisk:
    """One segment's score, with every term that made it."""

    segment_code: str
    length_m: float
    score: float
    terms: tuple[tuple[str, float], ...]

    @property
    def exposure(self) -> float:
        """Score weighted by how much pipe it applies to, in score kilometres."""
        return self.score * self.length_m / 1000.0

    def explain(self) -> str:
        """The multiplication written out."""
        parts = " x ".join(f"{name} {weight:.2f}" for name, weight in self.terms)
        return f"{self.segment_code}: {parts} = {self.score:.2f}"


def age_term(age_years: int) -> float:
    """How much the years in the ground count for."""
    if age_years < 0:
        raise ValidationError("a segment cannot be younger than nothing", age_years=age_years)
    return min(MAX_AGE_TERM, 1.0 + AGE_TERM_PER_DECADE * age_years / 10.0)


def staleness_term(years_since_survey: float | None) -> float:
    """How much never having looked counts for.

    A segment nobody has surveyed at all is treated as ten years stale rather
    than as infinitely stale. The point of the term is to move the next survey
    towards the pipe nobody has walked, and an unbounded term puts every one of
    them at the top in an order decided by nothing.
    """
    years = 10.0 if years_since_survey is None else years_since_survey
    if years < 0:
        raise ValidationError("a survey cannot be in the future", years=years)
    return min(MAX_STALENESS, 1.0 + UNSURVEYED_PER_YEAR * years)


def score_segment(
    segment: Segment,
    *,
    as_of: dt.date,
    years_since_survey: float | None = None,
    covered_share: float = 1.0,
) -> SegmentRisk:
    """Score one segment for where the next survey should go."""
    if not 0.0 <= covered_share <= 1.0:
        raise ValidationError("coverage is a share of the segment", value=covered_share)
    terms: list[tuple[str, float]] = [
        (
            f"age {as_of.year - segment.installed_year} years",
            age_term(as_of.year - segment.installed_year),
        ),
        ("time since survey", staleness_term(years_since_survey)),
    ]
    corrosivity = segment.corrosivity
    if corrosivity is None:
        terms.append(("soil unmeasured", UNKNOWN_SOIL_TERM))
    else:
        terms.append((f"soil {corrosivity}", SOIL_TERM[corrosivity]))
    terms.append(
        (f"class {int(segment.class_location)}", segment.class_location.priority_weight)
    )
    if segment.coating.shields_current:
        terms.append(("coating can shield", SHIELDING_TERM))
    if segment.protection is ProtectionMethod.UNPROTECTED:
        terms.append(("no protection on it", UNPROTECTED_TERM))
    if covered_share < 1.0:
        terms.append(
            (f"{1 - covered_share:.0%} out of reach", 1.0 + BLIND_TERM * (1.0 - covered_share))
        )
    score = 1.0
    for _, weight in terms:
        score *= weight
    return SegmentRisk(
        segment_code=segment.code,
        length_m=segment.length_m,
        score=score,
        terms=tuple(terms),
    )


def rank(scores: list[SegmentRisk]) -> list[SegmentRisk]:
    """Order segments by score, worst first."""
    return sorted(scores, key=lambda item: (-item.score, item.segment_code))


def by_exposure(scores: list[SegmentRisk]) -> list[SegmentRisk]:
    """Order segments by score weighted by length, which is where a budget goes."""
    return sorted(scores, key=lambda item: (-item.exposure, item.segment_code))


def total_exposure(scores: list[SegmentRisk]) -> float:
    """The whole line's exposure, for comparing one line against another."""
    return sum(item.exposure for item in scores)
