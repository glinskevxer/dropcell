"""Bonds, which are the wires that make an interference problem go away.

A bond is a cable between two structures, usually through a resistor, sometimes
through a diode so current can only run one way. It gives the stray current a
copper path home instead of an electrolytic one, and the whole of its value is
that it carries current. A bond that has gone open circuit looks exactly like a
bond that is working, from the outside, on a post nobody has opened in a year.

Some bonds are load bearing in a stronger sense. If the protection of a segment
depends on the bond being there, then losing the bond loses the segment, and
that bond is checked as often as a rectifier rather than as often as a test
post. Which bonds those are is a decision recorded when the bond goes in, not
something to work out later from potentials.

Direction is a fact about the bond, not an opinion. A bond sized to carry
current from our line to theirs, found carrying it the other way, has either
been wired backwards or the two systems have changed under it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station

OPEN_CIRCUIT_A = 0.01
DEFAULT_CURRENT_TOLERANCE = 0.4


class BondKind(StrEnum):
    """How a bond is built."""

    DIRECT = "direct"
    RESISTIVE = "resistive"
    DIODE = "diode"
    REVERSE_CURRENT_SWITCH = "reverse_current_switch"

    @property
    def is_one_way(self) -> bool:
        """Whether the bond is built to block current in one direction."""
        return self in {BondKind.DIODE, BondKind.REVERSE_CURRENT_SWITCH}


class BondHealth(StrEnum):
    """What a bond check concluded."""

    HEALTHY = "healthy"
    OPEN = "open"
    REVERSED = "reversed"
    OUT_OF_RANGE = "out_of_range"

    @property
    def is_fault(self) -> bool:
        """Whether somebody has to go and look at it."""
        return self is not BondHealth.HEALTHY


@dataclass(frozen=True)
class Bond:
    """One cable between two structures."""

    code: str
    line_code: str
    station: Station
    kind: BondKind
    to_structure: str
    installed_on: dt.date
    design_current_a: float
    resistor_ohm: float | None = None
    critical: bool = False
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="bond code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if not self.to_structure.strip():
            raise ValidationError("a bond has to go somewhere", code=self.code)
        object.__setattr__(self, "to_structure", self.to_structure.strip())
        if self.design_current_a <= 0:
            raise ValidationError("a bond is sized for a current", code=self.code)
        if self.kind is BondKind.RESISTIVE and self.resistor_ohm is None:
            raise ValidationError("a resistive bond needs its resistor value", code=self.code)
        if self.resistor_ohm is not None and self.resistor_ohm <= 0:
            raise ValidationError(
                "a bond resistor has to be positive",
                code=self.code,
                resistor_ohm=self.resistor_ohm,
            )

    @property
    def check_interval_days(self) -> int:
        """How often this bond has to be read.

        A critical bond is on the rectifier cycle because losing it loses the
        protection of everything behind it. Everything else is on the annual
        test point cycle.
        """
        return 75 if self.critical else 450


@dataclass(frozen=True)
class BondCheck:
    """One reading of the current in a bond."""

    bond_code: str
    checked_on: dt.date
    current_a: float
    reversed_polarity: bool = False
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bond_code", normalise_code(self.bond_code, kind="bond code"))

    @property
    def is_open(self) -> bool:
        """Whether the bond is passing effectively nothing."""
        return abs(self.current_a) <= OPEN_CIRCUIT_A


def assess_bond(
    bond: Bond,
    check: BondCheck,
    *,
    tolerance: float = DEFAULT_CURRENT_TOLERANCE,
) -> BondHealth:
    """Read one bond check against what the bond was built to do."""
    if not 0 < tolerance < 1:
        raise ValidationError(
            "the tolerance is a fraction of the design current", value=tolerance
        )
    if check.is_open:
        return BondHealth.OPEN
    if check.reversed_polarity:
        return BondHealth.REVERSED
    low = bond.design_current_a * (1.0 - tolerance)
    high = bond.design_current_a * (1.0 + tolerance)
    if not low <= abs(check.current_a) <= high:
        return BondHealth.OUT_OF_RANGE
    return BondHealth.HEALTHY


def critical_bonds(bonds: list[Bond]) -> list[Bond]:
    """Only the bonds whose loss takes protection with it."""
    return [bond for bond in bonds if bond.critical]


def overdue_bonds(
    bonds: list[Bond],
    last_checked: dict[str, dt.date],
    as_of: dt.date,
) -> list[Bond]:
    """Bonds that have gone past their own interval, worst overdue first."""
    late: list[tuple[int, Bond]] = []
    for bond in bonds:
        previous = last_checked.get(bond.code)
        if previous is None:
            late.append((10**6, bond))
            continue
        days = (as_of - previous).days
        if days > bond.check_interval_days:
            late.append((days - bond.check_interval_days, bond))
    return [bond for _, bond in sorted(late, key=lambda pair: (-pair[0], pair[1].code))]
