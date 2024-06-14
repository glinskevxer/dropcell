"""Crossings, where our current becomes somebody else's corrosion problem.

Two buried pipelines crossing at a road junction belong to two companies who
have never met. Our rectifier pushes current into the soil, some of it lands on
their line because their line is a good conductor lying across the field, and it
has to leave again somewhere. Where it leaves, their steel dissolves. Nothing
about our own readings shows this: our line is protected, our rectifier is
happy, and the damage is a mile away on a structure we do not own.

The test is a swing test. Ours is interrupted on a cycle while both structures
are read, and what matters is the direction the foreign line moves. If their
potential goes more positive while our unit is on, our current is discharging
off their pipe and we are causing them harm. If it goes more negative, they are
picking up protection from us at no cost. If it barely moves, there is nothing
to argue about.

The remedy is a bond, which is a deliberate metallic connection between the two
lines through a resistor, so the current returns to our system through copper
instead of through their steel. Sizing it is Ohm's law on the swing.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.model.testpoint import check_potential
from dropcell.stationing import Station

DEFAULT_SWING_LIMIT_MV = 20.0


class InterferenceVerdict(StrEnum):
    """What a swing test at a crossing concluded."""

    NONE = "none"
    HARMING_FOREIGN = "harming_foreign"
    HARMED_BY_FOREIGN = "harmed_by_foreign"
    BENEFICIAL = "beneficial"

    @property
    def needs_mitigation(self) -> bool:
        """Whether somebody has to install a bond or an anode."""
        return self in {
            InterferenceVerdict.HARMING_FOREIGN,
            InterferenceVerdict.HARMED_BY_FOREIGN,
        }

    @property
    def is_our_liability(self) -> bool:
        """Whether the cost of the remedy is ours to carry."""
        return self is InterferenceVerdict.HARMING_FOREIGN


@dataclass(frozen=True)
class Crossing:
    """A place where our line crosses somebody else's structure."""

    code: str
    line_code: str
    station: Station
    foreign_operator: str
    foreign_structure: str
    bonded: bool = False
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="crossing code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if not self.foreign_operator.strip():
            raise ValidationError("a crossing needs a foreign operator", code=self.code)
        object.__setattr__(self, "foreign_operator", self.foreign_operator.strip())


@dataclass(frozen=True)
class SwingTest:
    """One interruption test at a crossing."""

    crossing_code: str
    tested_on: dt.date
    foreign_with_ours_on_mv: float
    foreign_with_ours_off_mv: float
    ours_on_mv: float | None = None
    ours_off_mv: float | None = None
    their_rectifier_interrupted: bool = False
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "crossing_code", normalise_code(self.crossing_code, kind="crossing code")
        )
        check_potential(self.foreign_with_ours_on_mv, "foreign potential with ours on")
        check_potential(self.foreign_with_ours_off_mv, "foreign potential with ours off")
        if self.ours_on_mv is not None:
            check_potential(self.ours_on_mv, "our on potential")
        if self.ours_off_mv is not None:
            check_potential(self.ours_off_mv, "our off potential")

    @property
    def foreign_swing_mv(self) -> float:
        """How far the foreign structure moves when our unit switches on.

        Positive means it goes less negative with our current flowing, which is
        current leaving their steel. Negative means they are picking up
        protection from us.
        """
        return self.foreign_with_ours_on_mv - self.foreign_with_ours_off_mv

    @property
    def our_swing_mv(self) -> float | None:
        """How far our own line moves, when it was read at all."""
        if self.ours_on_mv is None or self.ours_off_mv is None:
            return None
        return self.ours_on_mv - self.ours_off_mv


@dataclass(frozen=True)
class InterferenceAssessment:
    """What a swing test was read as."""

    crossing_code: str
    verdict: InterferenceVerdict
    foreign_swing_mv: float
    limit_mv: float
    reason: str


def classify_swing(
    test: SwingTest,
    *,
    limit_mv: float = DEFAULT_SWING_LIMIT_MV,
) -> InterferenceAssessment:
    """Read one swing test at a crossing."""
    if limit_mv <= 0:
        raise ValidationError("the swing limit has to be positive", limit_mv=limit_mv)
    swing = test.foreign_swing_mv
    if swing > limit_mv:
        verdict = InterferenceVerdict.HARMING_FOREIGN
        reason = "our current is discharging off their structure"
    elif swing < -limit_mv:
        verdict = InterferenceVerdict.BENEFICIAL
        reason = "their structure is picking up protection from our system"
    else:
        verdict = InterferenceVerdict.NONE
        reason = "the foreign structure barely moves with our unit"
    if test.their_rectifier_interrupted and swing > limit_mv:
        verdict = InterferenceVerdict.HARMED_BY_FOREIGN
        reason = "the swing appeared with their unit interrupted, so the current is theirs"
    return InterferenceAssessment(
        crossing_code=test.crossing_code,
        verdict=verdict,
        foreign_swing_mv=swing,
        limit_mv=limit_mv,
        reason=reason,
    )


def bond_resistance_ohm(swing_mv: float, bond_current_a: float) -> float:
    """The resistor a bond needs so it carries the current the swing implies."""
    if bond_current_a <= 0:
        raise ValidationError("bond current must be positive", bond_current_a=bond_current_a)
    if swing_mv <= 0:
        raise ValidationError(
            "a bond is only sized against a positive swing", swing_mv=swing_mv
        )
    return (swing_mv / 1000.0) / bond_current_a
