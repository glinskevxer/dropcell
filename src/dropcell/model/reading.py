"""One visit to one lead, and the arithmetic that falls out of it.

Split out of the test post module once the two had grown apart. A post is a
thing in a field with a fixed position and a fixed set of wires, and it changes
about twice in fifty years. A reading is a measurement with a date, an
electrode and a technician's name on it, and there are tens of thousands of
them. Keeping both in one file meant every change to the reading shape touched
the module the whole package imports for the post.

The ``on`` potential is what the pipe sits at with everything running. The
``off`` potential is what it sits at in the moment after every current source
has been interrupted together, before the polarisation has had time to decay.
The difference between them is the IR drop in the soil, which is voltage the
pipe never actually sees, and which is why the ``on`` number flatters the line.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.electrodes import Electrode, to_cse
from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.ids import normalise_code

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
