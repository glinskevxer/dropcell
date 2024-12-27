"""Ranking the digs, which is where every other number in here ends up.

A survey produces more defects than anybody is going to excavate this year, so
the whole programme comes down to which twenty get dug. That decision is made
badly almost everywhere, usually by sorting on the survey's own severity number
and stopping there, which ignores that the same defect is a different problem
in wet clay under a housing estate than in dry sand under a field.

The score is a product rather than a sum. A sum lets a large value in one term
carry a finding that is trivial in every other, and the arithmetic that produces
is a category one indication under a school outranking a category four in a
field because the school scored high on one factor. A product cannot do that: a
term near one leaves the score near what the other terms said.

Nothing here is calibrated against anything. It is a way of writing down what
the engineer already believes so that two people ranking the same list get the
same order, and so that the ranking can be argued with by changing a number
instead of by arguing about a list.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.enums import Commodity, SoilCorrosivity
from dropcell.model.segment import Segment
from dropcell.survey.dcvg import DcvgCategory

CATEGORY_WEIGHT: dict[DcvgCategory, float] = {
    DcvgCategory.ONE: 1.0,
    DcvgCategory.TWO: 1.6,
    DcvgCategory.THREE: 2.6,
    DcvgCategory.FOUR: 4.0,
}

SOIL_WEIGHT: dict[SoilCorrosivity, float] = {
    SoilCorrosivity.VERY_CORROSIVE: 2.0,
    SoilCorrosivity.CORROSIVE: 1.6,
    SoilCorrosivity.MODERATE: 1.2,
    SoilCorrosivity.MILD: 1.0,
    SoilCorrosivity.BENIGN: 0.8,
}

UNKNOWN_SOIL_WEIGHT = 1.3
SHIELDING_WEIGHT = 1.5
ANODIC_WEIGHT = 2.0
SHALLOW_COVER_M = 0.9
SHALLOW_WEIGHT = 1.3


class DigBand(StrEnum):
    """What a score means for a work plan."""

    ROUTINE = "routine"
    PLANNED = "planned"
    PRIORITY = "priority"
    IMMEDIATE = "immediate"

    @property
    def rank(self) -> int:
        """An order to sort by."""
        return {"routine": 1, "planned": 2, "priority": 3, "immediate": 4}[self.value]


BANDS: list[tuple[float, DigBand]] = [
    (2.0, DigBand.ROUTINE),
    (4.0, DigBand.PLANNED),
    (8.0, DigBand.PRIORITY),
]


def band_for(score: float) -> DigBand:
    """Put a score in the band a work plan is built from."""
    if score < 0:
        raise ValidationError("a priority score cannot be negative", score=score)
    for limit, band in BANDS:
        if score < limit:
            return band
    return DigBand.IMMEDIATE


@dataclass(frozen=True)
class PriorityScore:
    """One defect's score, with every term that made it."""

    reference: str
    score: float
    terms: tuple[tuple[str, float], ...]

    @property
    def band(self) -> DigBand:
        """The band this score falls in."""
        return band_for(self.score)

    def explain(self) -> str:
        """The multiplication written out, which is the point of the exercise."""
        parts = " x ".join(f"{name} {weight:.2f}" for name, weight in self.terms)
        return f"{self.reference}: {parts} = {self.score:.2f} ({self.band})"


def score_defect(
    reference: str,
    *,
    category: DcvgCategory,
    segment: Segment,
    commodity: Commodity = Commodity.NATURAL_GAS,
    anodic: bool = False,
    age_years: int | None = None,
) -> PriorityScore:
    """Score one coating defect for the dig list."""
    terms: list[tuple[str, float]] = [("category", CATEGORY_WEIGHT[category])]
    corrosivity = segment.corrosivity
    if corrosivity is None:
        terms.append(("soil unmeasured", UNKNOWN_SOIL_WEIGHT))
    else:
        terms.append((f"soil {corrosivity}", SOIL_WEIGHT[corrosivity]))
    terms.append(
        (f"class {int(segment.class_location)}", segment.class_location.priority_weight)
    )
    if segment.coating.shields_current:
        terms.append(("shielding coating", SHIELDING_WEIGHT))
    if segment.depth_of_cover_m < SHALLOW_COVER_M:
        terms.append(("shallow cover", SHALLOW_WEIGHT))
    if anodic:
        terms.append(("current leaving", ANODIC_WEIGHT))
    if commodity.is_hazardous_liquid:
        terms.append(("liquid release", 1.3))
    if age_years is not None and age_years >= 50:
        terms.append(("over fifty years old", 1.2))
    score = 1.0
    for _, weight in terms:
        score *= weight
    return PriorityScore(reference=reference, score=score, terms=tuple(terms))


def rank(scores: list[PriorityScore]) -> list[PriorityScore]:
    """Order a dig list, worst first."""
    return sorted(scores, key=lambda item: (-item.score, item.reference))


def in_band(scores: list[PriorityScore], band: DigBand) -> list[PriorityScore]:
    """Only the defects in one band."""
    return [item for item in scores if item.band is band]


def dig_list(scores: list[PriorityScore], budget: int) -> list[PriorityScore]:
    """The worst n defects, which is what a year's budget actually buys."""
    if budget < 0:
        raise ValidationError("a dig budget cannot be negative", budget=budget)
    return rank(scores)[:budget]


def age_of(segment: Segment, as_of: dt.date) -> int:
    """How long the segment has been in the ground."""
    return as_of.year - segment.installed_year
