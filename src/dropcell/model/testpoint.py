"""Test posts, and the readings taken at them.

A test post is a plastic tube at the fence line with a terminal board in the
top and a bundle of wires running down to the pipe. It is the only place a
potential can be read without digging, so the whole monitoring programme is
built around where the posts are and what each wire in them goes to.

A reading is one visit to one lead. The ``on`` potential is what the pipe sits
at with everything running. The ``off`` potential is what it sits at in the
moment after every current source has been interrupted together, before the
polarisation has had time to decay. The difference between them is the IR drop
in the soil, which is voltage the pipe never actually sees, and which is why the
``on`` number flatters the line.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.electrodes import Electrode, to_cse
from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station

POTENTIAL_FLOOR_MV = -3000.0
POTENTIAL_CEILING_MV = 1000.0


def check_potential(millivolts: float, label: str) -> float:
    """Refuse a potential that no half cell in soil could have produced."""
    if not POTENTIAL_FLOOR_MV <= millivolts <= POTENTIAL_CEILING_MV:
        raise ValidationError(
            f"{label} is outside anything a buried pipe reads",
            value=millivolts,
            floor_mv=POTENTIAL_FLOOR_MV,
            ceiling_mv=POTENTIAL_CEILING_MV,
        )
    return millivolts


@dataclass(frozen=True)
class TestPoint:
    """One post on the line, with the leads it carries."""

    code: str
    line_code: str
    station: Station
    leads: frozenset[LeadKind]
    installed_on: dt.date
    description: str = field(default="", compare=False)
    permanent_reference_cell: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="test point code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        object.__setattr__(self, "leads", frozenset(self.leads))
        if not self.leads:
            raise ValidationError(
                "a test point with no leads is a plastic tube", code=self.code
            )

    @property
    def reads_structure(self) -> bool:
        """Whether any lead here reads a potential on our own steel."""
        return any(lead.carries_structure_potential for lead in self.leads)

    def has(self, lead: LeadKind) -> bool:
        """Whether the post carries that lead."""
        return lead in self.leads

    def require_lead(self, lead: LeadKind) -> LeadKind:
        """Return the lead, or refuse it if this post does not carry it."""
        if lead not in self.leads:
            raise ValidationError(
                "this post does not carry that lead",
                code=self.code,
                lead=str(lead),
                leads=sorted(str(item) for item in self.leads),
            )
        return lead


@dataclass(frozen=True)
class Reading:
    """One visit to one lead at one post."""

    test_point_code: str
    lead: LeadKind
    taken_on: dt.date
    on_mv: float
    off_mv: float | None = None
    native_mv: float | None = None
    electrode: Electrode = Electrode.CSE
    cell_serial: str = ""
    technician: str = ""
    comment: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "test_point_code",
            normalise_code(self.test_point_code, kind="test point code"),
        )
        check_potential(self.on_mv, "on potential")
        if self.off_mv is not None:
            check_potential(self.off_mv, "off potential")
        if self.native_mv is not None:
            check_potential(self.native_mv, "native potential")

    @property
    def is_interrupted(self) -> bool:
        """Whether this visit caught an instant off potential."""
        return self.off_mv is not None

    @property
    def on_cse_mv(self) -> float:
        """The on potential restated against copper/copper sulfate."""
        return to_cse(self.on_mv, self.electrode)

    @property
    def off_cse_mv(self) -> float | None:
        """The off potential restated against copper/copper sulfate."""
        if self.off_mv is None:
            return None
        return to_cse(self.off_mv, self.electrode)

    @property
    def ir_drop_mv(self) -> float | None:
        """Voltage in the soil that the on reading includes and the pipe never sees."""
        if self.off_mv is None:
            return None
        return self.on_mv - self.off_mv

    @property
    def polarisation_mv(self) -> float | None:
        """How far the off potential sits below the pipe's own native potential."""
        if self.off_mv is None or self.native_mv is None:
            return None
        return self.native_mv - self.off_mv
