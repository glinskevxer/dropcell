"""How the work is shared between the units on a line.

A line with four rectifiers and a comfortable protection rate can be a line
with four rectifiers or a line with one rectifier and three ornaments. The
protection figures cannot tell those apart, because both of them read the same
until the one that is working fails.

Three things are worth knowing and none of them is on any other page. How much
of the total current one unit is putting out. Whether that unit has any headroom
left if a neighbour goes down. And how far apart the units are, because a unit
whose nearest neighbour is fifteen kilometres away cannot cover for it however
much rating it has.

The concentration figure is the share the largest single unit is carrying. On a
line where every unit is pulling the same weight it is one over the number of
units; on a line carried by one it is one. It is the quickest way to see a
system that is not what its drawing says it is.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.rectifier import Rectifier, RectifierCheck

CONCENTRATED_SHARE = 0.6
NO_HEADROOM_FRACTION = 0.85


@dataclass(frozen=True)
class UnitShare:
    """One unit's part of the line's current."""

    tag: str
    station_m: float
    rated_a: float
    output_a: float
    share: float

    @property
    def load(self) -> float:
        """Output as a fraction of the nameplate."""
        return 0.0 if self.rated_a <= 0 else self.output_a / self.rated_a

    @property
    def spare_a(self) -> float:
        """How much more it could put out before it runs out of rating."""
        return max(0.0, self.rated_a - self.output_a)

    @property
    def is_dead(self) -> bool:
        """Whether it is putting out nothing at all."""
        return self.output_a <= 0.05

    @property
    def has_headroom(self) -> bool:
        """Whether it has enough left to take on somebody else's work."""
        return self.load < NO_HEADROOM_FRACTION


@dataclass(frozen=True)
class LineBalance:
    """How the units on one line share the work."""

    line_code: str
    units: tuple[UnitShare, ...]

    @property
    def total_a(self) -> float:
        """Everything the line is drawing."""
        return sum(item.output_a for item in self.units)

    @property
    def working(self) -> tuple[UnitShare, ...]:
        """The units that are actually putting out current."""
        return tuple(item for item in self.units if not item.is_dead)

    @property
    def dead(self) -> tuple[UnitShare, ...]:
        """The units that are not."""
        return tuple(item for item in self.units if item.is_dead)

    @property
    def concentration(self) -> float:
        """The share the largest single unit is carrying."""
        if not self.units or self.total_a <= 0:
            return 0.0
        return max(item.share for item in self.units)

    @property
    def is_concentrated(self) -> bool:
        """Whether one unit is carrying most of the line."""
        return self.concentration > CONCENTRATED_SHARE and len(self.units) > 1

    @property
    def spare_a(self) -> float:
        """How much rating is left across every unit that has any."""
        return sum(item.spare_a for item in self.units if item.has_headroom)

    @property
    def can_lose_the_biggest(self) -> bool:
        """Whether the rest could take up the largest unit's output.

        This is the question a system is designed against and the one nobody
        checks after it is built. It is not a full answer, because current does
        not go where there is rating, it goes where the resistance lets it. It
        is a necessary condition, and a line that fails it fails it regardless
        of geometry.
        """
        if not self.working:
            return False
        biggest = max(self.units, key=lambda item: item.output_a)
        others = sum(
            item.spare_a for item in self.units if item.tag != biggest.tag and item.has_headroom
        )
        return others >= biggest.output_a

    def widest_gap_m(self) -> float | None:
        """The furthest any two neighbouring units sit apart."""
        if len(self.units) < 2:
            return None
        positions = sorted(item.station_m for item in self.units)
        return max(
            later - earlier for earlier, later in zip(positions, positions[1:], strict=False)
        )

    def summary(self) -> str:
        """One line for the top of a report."""
        return (
            f"{self.line_code}: {len(self.working)} of {len(self.units)} units working, "
            f"{self.total_a:.2f} A in total, "
            f"largest carrying {self.concentration:.0%}"
        )


def balance(
    units: list[Rectifier],
    latest: Mapping[str, RectifierCheck | None],
) -> LineBalance:
    """Work out how the units on a line are sharing the load."""
    if not units:
        raise ValidationError("there are no units on that line to balance")
    outputs = {
        unit.tag: 0.0 if latest.get(unit.tag) is None else latest[unit.tag].output_current_a  # type: ignore[union-attr]
        for unit in units
    }
    total = sum(outputs.values())
    return LineBalance(
        line_code=units[0].line_code,
        units=tuple(
            UnitShare(
                tag=unit.tag,
                station_m=unit.station.metres,
                rated_a=unit.rated_current_a,
                output_a=outputs[unit.tag],
                share=0.0 if total <= 0 else outputs[unit.tag] / total,
            )
            for unit in units
        ),
    )
