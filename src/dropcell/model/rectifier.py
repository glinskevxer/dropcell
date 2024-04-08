"""Rectifiers, the boxes that push the current onto an impressed current system.

A rectifier takes mains AC, drops it through a tapped transformer, rectifies it
and feeds the negative side to the pipe and the positive side to a groundbed.
The taps are coarse and fine links on a board, so output is adjusted in steps
rather than continuously, and a unit sitting on its last tap has nothing left to
give when the coating degrades further.

Units are checked several times a year. The check is quick, it is mostly a
matter of reading a panel meter and looking for a blown fuse, and its whole
value is that a failed rectifier is otherwise invisible until the next survey
finds a mile of unprotected pipe.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station

OFF_CURRENT_A = 0.05
NEAR_CAPACITY_FRACTION = 0.85


@dataclass(frozen=True)
class Rectifier:
    """One impressed current unit."""

    tag: str
    line_code: str
    station: Station
    groundbed_code: str
    rated_voltage_v: float
    rated_current_a: float
    coarse_taps: int
    fine_taps: int
    installed_on: dt.date
    interrupter_fitted: bool = True
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tag", normalise_code(self.tag, kind="rectifier tag"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        object.__setattr__(
            self, "groundbed_code", normalise_code(self.groundbed_code, kind="groundbed code")
        )
        if self.rated_voltage_v <= 0 or self.rated_current_a <= 0:
            raise ValidationError(
                "a rectifier has to be rated for some output",
                tag=self.tag,
                rated_voltage_v=self.rated_voltage_v,
                rated_current_a=self.rated_current_a,
            )
        if self.coarse_taps < 1 or self.fine_taps < 1:
            raise ValidationError("tap counts start at one", tag=self.tag)

    @property
    def rated_power_w(self) -> float:
        """Nameplate output."""
        return self.rated_voltage_v * self.rated_current_a

    @property
    def tap_positions(self) -> int:
        """How many distinct settings the tap board offers."""
        return self.coarse_taps * self.fine_taps

    def is_valid_tap(self, coarse: int, fine: int) -> bool:
        """Whether a tap pair exists on this unit's board."""
        return 1 <= coarse <= self.coarse_taps and 1 <= fine <= self.fine_taps


@dataclass(frozen=True)
class RectifierCheck:
    """One visit to a rectifier."""

    rectifier_tag: str
    checked_on: dt.date
    output_voltage_v: float
    output_current_a: float
    coarse_tap: int
    fine_tap: int
    hour_meter: float | None = None
    technician: str = ""
    comment: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "rectifier_tag", normalise_code(self.rectifier_tag, kind="rectifier tag")
        )
        if self.output_voltage_v < 0 or self.output_current_a < 0:
            raise ValidationError(
                "a rectifier output cannot be negative",
                tag=self.rectifier_tag,
                output_voltage_v=self.output_voltage_v,
                output_current_a=self.output_current_a,
            )
        if self.hour_meter is not None and self.hour_meter < 0:
            raise ValidationError("hour meters do not run backwards", tag=self.rectifier_tag)

    @property
    def output_power_w(self) -> float:
        """What the unit was actually delivering."""
        return self.output_voltage_v * self.output_current_a

    @property
    def is_off(self) -> bool:
        """Whether the unit was effectively dead when it was read."""
        return self.output_current_a <= OFF_CURRENT_A

    @property
    def circuit_resistance_ohm(self) -> float | None:
        """Whole circuit resistance, which climbs as a groundbed dries or wears."""
        if self.output_current_a <= OFF_CURRENT_A:
            return None
        return self.output_voltage_v / self.output_current_a

    def load_fraction(self, rectifier: Rectifier) -> float:
        """Output as a fraction of the nameplate current."""
        return self.output_current_a / rectifier.rated_current_a

    def is_near_capacity(self, rectifier: Rectifier) -> bool:
        """Whether the unit has little headroom left before it needs replacing."""
        return self.load_fraction(rectifier) >= NEAR_CAPACITY_FRACTION

    def tap_is_valid_for(self, rectifier: Rectifier) -> bool:
        """Whether the tap pair written on the sheet exists on that unit."""
        return rectifier.is_valid_tap(self.coarse_tap, self.fine_tap)
