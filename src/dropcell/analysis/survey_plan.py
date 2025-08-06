"""Spending a survey budget, which is the decision the rest of this feeds.

A close interval survey costs by the kilometre and a year buys a fixed number
of them. Every other page here describes a state; this one turns those states
into a list of which kilometres to walk, and it is the only place in the tool
where a number has money behind it.

The greedy choice is by score rather than by exposure. Exposure is score times
length, and picking on exposure spends the whole budget on the longest segments
whatever their condition, which is how a programme ends up walking the same
easy transmission line every year. Picking on score walks the worst pipe first
and stops when the budget runs out, which is what the budget is for.

A segment that does not fit in what is left of the budget is skipped rather
than part walked. Half a close interval survey is not half the evidence: the
sections it would have found are the ones it did not reach.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.analysis.risk import SegmentRisk, rank
from dropcell.errors import ValidationError


@dataclass(frozen=True)
class PlannedSurvey:
    """One segment on the plan."""

    segment_code: str
    line_code: str
    length_m: float
    score: float

    @property
    def length_km(self) -> float:
        """How much walking it is."""
        return self.length_m / 1000.0


@dataclass(frozen=True)
class SurveyPlan:
    """A year's walking, and what it did not reach."""

    budget_km: float
    walking: tuple[PlannedSurvey, ...]
    skipped: tuple[PlannedSurvey, ...]

    @property
    def planned_km(self) -> float:
        """How much of the budget the plan uses."""
        return sum(item.length_km for item in self.walking)

    @property
    def spare_km(self) -> float:
        """How much is left over, which is never nothing on a real line."""
        return max(0.0, self.budget_km - self.planned_km)

    @property
    def skipped_km(self) -> float:
        """How much pipe the budget did not reach."""
        return sum(item.length_km for item in self.skipped)

    @property
    def worst_skipped(self) -> PlannedSurvey | None:
        """The worst segment the budget did not reach, which is the argument for more."""
        return max(self.skipped, key=lambda item: item.score) if self.skipped else None

    def summary(self) -> str:
        """One line for whoever signs the budget off."""
        said = (
            f"{len(self.walking)} segments, {self.planned_km:.1f} km of "
            f"{self.budget_km:.1f} km budgeted"
        )
        if self.skipped:
            said += f", {len(self.skipped)} segments and {self.skipped_km:.1f} km not reached"
        return said


def plan_surveys(
    scores: list[SegmentRisk],
    line_codes: dict[str, str],
    *,
    budget_km: float,
) -> SurveyPlan:
    """Fill a survey budget with the worst pipe that fits in it."""
    if budget_km < 0:
        raise ValidationError("a survey budget cannot be negative", budget_km=budget_km)
    walking: list[PlannedSurvey] = []
    skipped: list[PlannedSurvey] = []
    remaining = budget_km
    for score in rank(scores):
        item = PlannedSurvey(
            segment_code=score.segment_code,
            line_code=line_codes.get(score.segment_code, ""),
            length_m=score.length_m,
            score=score.score,
        )
        if item.length_km <= remaining:
            walking.append(item)
            remaining -= item.length_km
        else:
            skipped.append(item)
    return SurveyPlan(budget_km=budget_km, walking=tuple(walking), skipped=tuple(skipped))


def budget_for(scores: list[SegmentRisk], *, above_score: float) -> float:
    """How much budget it would take to walk everything above a score.

    The other direction, and the one that turns a plan into an argument. A
    programme that wants every segment over a given score walked can be told
    what that costs before anybody has to decide whether it is worth it.
    """
    if above_score < 0:
        raise ValidationError("a score threshold cannot be negative", value=above_score)
    return sum(item.length_m for item in scores if item.score >= above_score) / 1000.0
