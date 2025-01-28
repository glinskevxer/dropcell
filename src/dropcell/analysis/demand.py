"""How much current a line needs, and whether what is installed can supply it.

The demand is an area multiplied by a current density and nothing more. The
area is known to a few percent from the drawings. The density is a table value
for a coating in good condition, and the coating is not in good condition,
which is where all the uncertainty is.

Coating degrades and the honest way to carry that is a breakdown factor that
grows with age. A ten year old epoxy line is drawing a few percent more than it
did new; a fifty year old tape wrapped line is drawing many times more, and the
table value for tape wrap in good condition describes a pipe that has not
existed for decades.

The comparison at the end is the useful part. A system whose installed capacity
is under the demand cannot protect the line however it is adjusted, and no
amount of survey work will change that. It is worth knowing before somebody
spends a year investigating why the far end will not come up.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.rectifier import Rectifier
from dropcell.model.segment import Segment

DEFAULT_DESIGN_FACTOR = 1.25
BREAKDOWN_PER_YEAR = 0.02
MAX_BREAKDOWN = 8.0


def breakdown_factor(age_years: int, *, per_year: float = BREAKDOWN_PER_YEAR) -> float:
    """How much more current a coating draws than it did when it was new."""
    if age_years < 0:
        raise ValidationError("a coating cannot be younger than nothing", age_years=age_years)
    if per_year < 0:
        raise ValidationError("coating does not improve with age", per_year=per_year)
    return min(MAX_BREAKDOWN, 1.0 + per_year * age_years)


@dataclass(frozen=True)
class SegmentDemand:
    """What one segment asks of the system."""

    segment_code: str
    area_m2: float
    new_current_ma: float
    breakdown: float

    @property
    def current_ma(self) -> float:
        """What the segment draws now, with the coating in the state it is in."""
        return self.new_current_ma * self.breakdown

    @property
    def current_a(self) -> float:
        """The same number in the unit a rectifier is rated in."""
        return self.current_ma / 1000.0


@dataclass(frozen=True)
class LineDemand:
    """What a whole line asks, against what is installed to supply it."""

    line_code: str
    segments: tuple[SegmentDemand, ...]
    installed_a: float
    design_factor: float

    @property
    def bare_demand_a(self) -> float:
        """What the line draws now, with no allowance for anything."""
        return sum(item.current_a for item in self.segments)

    @property
    def design_demand_a(self) -> float:
        """What a system should be sized for, with the design allowance on top."""
        return self.bare_demand_a * self.design_factor

    @property
    def headroom_a(self) -> float:
        """How much rated output is left over the design demand."""
        return self.installed_a - self.design_demand_a

    @property
    def is_short(self) -> bool:
        """Whether the installed capacity cannot meet the design demand."""
        return self.headroom_a < 0

    @property
    def cannot_protect(self) -> bool:
        """Whether the installed capacity cannot even meet the bare demand.

        This is the one that matters. Short of the design demand is a system
        with no margin, which is a planning problem. Short of the bare demand is
        a system that cannot protect the line at any tap setting, which is a
        capital problem, and the two get reported as the same thing far too
        often.
        """
        return self.installed_a < self.bare_demand_a

    @property
    def utilisation(self) -> float:
        """Bare demand as a share of installed capacity."""
        if self.installed_a <= 0:
            return float("inf") if self.bare_demand_a > 0 else 0.0
        return self.bare_demand_a / self.installed_a

    def worst_first(self) -> tuple[SegmentDemand, ...]:
        """Segments ordered by how much they are asking for."""
        return tuple(
            sorted(self.segments, key=lambda item: (-item.current_a, item.segment_code))
        )


def segment_demand(segment: Segment, *, as_of_year: int) -> SegmentDemand:
    """What one segment draws, given how old its coating is."""
    age = max(0, as_of_year - segment.installed_year)
    return SegmentDemand(
        segment_code=segment.code,
        area_m2=segment.external_area_m2,
        new_current_ma=segment.design_current_ma,
        breakdown=breakdown_factor(age),
    )


def line_demand(
    line_code: str,
    segments: list[Segment],
    rectifiers: list[Rectifier],
    *,
    as_of_year: int,
    design_factor: float = DEFAULT_DESIGN_FACTOR,
) -> LineDemand:
    """Add a line's segments up and set the total against what is installed."""
    if design_factor < 1.0:
        raise ValidationError(
            "a design factor below one is not an allowance", design_factor=design_factor
        )
    return LineDemand(
        line_code=line_code,
        segments=tuple(segment_demand(item, as_of_year=as_of_year) for item in segments),
        installed_a=sum(unit.rated_current_a for unit in rectifiers),
        design_factor=design_factor,
    )
