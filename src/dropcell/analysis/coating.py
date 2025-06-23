"""What the current draw says about the coating, which nothing else measures.

Every other figure in here describes the potential, and the potential says
whether the pipe is protected today. None of it says anything about the state
of the coating, which is what decides whether it will still be protected in ten
years and what the next rectifier will cost.

The current does. A segment drawing four times what its coating should draw is
a segment whose coating has four times as much steel exposed as it did new, and
that comparison needs nothing but the drawings and a clamp meter.

The number that comes out is a breakdown factor, and it is worth being careful
about what it means. It is not a percentage of coating that has fallen off. It
is the ratio of the current the segment actually needs to the current a
perfect coating of that type would need, and on a well coated line a factor of
twenty is normal and describes a coating in good condition with a few defects
in it.

The implied bare area is worse still as a figure and is here anyway, because it
is the one people ask for. It assumes every extra milliamp is going into bare
steel at the bare steel current density, which is not true and produces a
number that is right to within a factor of a few. It is labelled accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.enums import CoatingType
from dropcell.model.segment import Segment

BARE_DENSITY_MA_PER_M2 = 21.5
WELL_COATED = 5.0
DEGRADED = 25.0
POOR = 100.0


@dataclass(frozen=True)
class CoatingCondition:
    """What one segment's current draw says about its coating."""

    segment_code: str
    coating: CoatingType
    area_m2: float
    design_current_ma: float
    measured_current_ma: float

    @property
    def breakdown_factor(self) -> float:
        """How many times the design current the segment is actually drawing."""
        return self.measured_current_ma / self.design_current_ma

    @property
    def excess_current_ma(self) -> float:
        """The current above what a perfect coating would need."""
        return max(0.0, self.measured_current_ma - self.design_current_ma)

    @property
    def implied_bare_area_m2(self) -> float:
        """Bare steel that would account for the excess, to within a factor of a few."""
        return self.excess_current_ma / BARE_DENSITY_MA_PER_M2

    @property
    def implied_bare_share(self) -> float:
        """That area as a share of the segment, which is the figure people quote."""
        return self.implied_bare_area_m2 / self.area_m2

    @property
    def verdict(self) -> str:
        """A word for the coating, with the bands stated on the page."""
        factor = self.breakdown_factor
        if factor <= WELL_COATED:
            return "as laid"
        if factor <= DEGRADED:
            return "sound with defects"
        if factor <= POOR:
            return "degraded"
        return "failed"

    @property
    def is_worth_investigating(self) -> bool:
        """Whether the draw is far enough off to be worth a gradient survey."""
        return self.breakdown_factor > DEGRADED

    def explain(self) -> str:
        """One line saying what the comparison was."""
        return (
            f"{self.segment_code}: drawing {self.measured_current_ma:.0f} mA against "
            f"{self.design_current_ma:.1f} mA for {self.coating} as laid, "
            f"a factor of {self.breakdown_factor:.0f} ({self.verdict})"
        )


def assess_coating(segment: Segment, measured_current_ma: float) -> CoatingCondition:
    """Compare what a segment draws against what its coating should draw."""
    if measured_current_ma < 0:
        raise ValidationError(
            "a segment cannot draw a negative current",
            code=segment.code,
            measured_current_ma=measured_current_ma,
        )
    design = segment.design_current_ma
    if design <= 0:
        raise ValidationError("that coating has no design current", code=segment.code)
    return CoatingCondition(
        segment_code=segment.code,
        coating=segment.coating,
        area_m2=segment.external_area_m2,
        design_current_ma=design,
        measured_current_ma=measured_current_ma,
    )


def share_out(segments: list[Segment], total_current_ma: float) -> dict[str, float]:
    """Split a rectifier's output across the segments it feeds, by design current.

    This is a guess and it is stated as one. A unit feeding four segments does
    not divide its output evenly and it does not divide it by area either; it
    divides it by wherever the current can get to, which depends on the coating
    and on the soil between the drain point and the pipe. Design current is the
    least wrong of the easy assumptions, because it already carries the coating.
    """
    if total_current_ma < 0:
        raise ValidationError("a rectifier cannot draw a negative current")
    weights = {segment.code: segment.design_current_ma for segment in segments}
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValidationError("those segments have no design current between them")
    return {code: total_current_ma * weight / total_weight for code, weight in weights.items()}


def worst_first(conditions: list[CoatingCondition]) -> list[CoatingCondition]:
    """Order segments by how far their draw is off, worst first."""
    return sorted(conditions, key=lambda item: (-item.breakdown_factor, item.segment_code))
