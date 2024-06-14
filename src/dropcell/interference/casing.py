"""Casings, and the three ways a road crossing can go wrong.

Where a line goes under a road or a railway it is usually run inside a larger
steel sleeve. The sleeve takes the load and lets the carrier pipe be pulled out
one day, and it is meant to be electrically separate from the pipe inside it.
When it is not, the protective current goes onto the casing instead, and the
carrier pipe inside the crossing is left bare in a damp annulus with no
protection and no way to inspect it. It is one of the few places a line can be
completely unprotected while every test post either side reads perfectly.

Three states, and telling them apart is the whole job.

A clear casing sits near the native potential of buried steel while the carrier
pipe sits at its protected potential, so the two readings are far apart.

An electrolytic short means the annulus has filled with water and current is
passing through it. The casing is dragged part of the way towards the carrier
potential, so the gap narrows, and the crossing is corroding slowly.

A metallic short means the two are touching. They then read as one structure,
the gap collapses to almost nothing, and both move together when the rectifier
is interrupted. That is the one that needs a crew this month.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.model.testpoint import check_potential
from dropcell.stationing import Station

METALLIC_SHORT_MV = 10.0
ELECTROLYTIC_MV = 100.0
NATIVE_STEEL_MV = -550.0


class CasingStatus(StrEnum):
    """What the readings say about the annulus."""

    CLEAR = "clear"
    ELECTROLYTIC = "electrolytic"
    METALLIC_SHORT = "metallic_short"
    INDETERMINATE = "indeterminate"

    @property
    def needs_work(self) -> bool:
        """Whether this state puts the crossing on a work list."""
        return self in {CasingStatus.ELECTROLYTIC, CasingStatus.METALLIC_SHORT}

    @property
    def response_days(self) -> int | None:
        """How long there is before it has to be dealt with."""
        return _RESPONSE_DAYS[self]


_RESPONSE_DAYS: dict[CasingStatus, int | None] = {
    CasingStatus.CLEAR: None,
    CasingStatus.ELECTROLYTIC: 365,
    CasingStatus.METALLIC_SHORT: 90,
    CasingStatus.INDETERMINATE: 60,
}


@dataclass(frozen=True)
class CasingTest:
    """One visit to a cased crossing."""

    casing_code: str
    line_code: str
    station: Station
    tested_on: dt.date
    pipe_on_mv: float
    casing_on_mv: float
    pipe_off_mv: float | None = None
    casing_off_mv: float | None = None
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "casing_code", normalise_code(self.casing_code, kind="casing code")
        )
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        check_potential(self.pipe_on_mv, "pipe on potential")
        check_potential(self.casing_on_mv, "casing on potential")
        if self.pipe_off_mv is not None:
            check_potential(self.pipe_off_mv, "pipe off potential")
        if self.casing_off_mv is not None:
            check_potential(self.casing_off_mv, "casing off potential")

    @property
    def interrupted(self) -> bool:
        """Whether both structures were read with the current switched off."""
        return self.pipe_off_mv is not None and self.casing_off_mv is not None

    @property
    def separation_mv(self) -> float:
        """How far apart the two structures sit, on the best readings available."""
        if self.pipe_off_mv is not None and self.casing_off_mv is not None:
            return abs(self.pipe_off_mv - self.casing_off_mv)
        return abs(self.pipe_on_mv - self.casing_on_mv)

    @property
    def moves_together(self) -> bool | None:
        """Whether both structures shifted by the same amount on interruption."""
        if not self.interrupted:
            return None
        assert self.pipe_off_mv is not None
        assert self.casing_off_mv is not None
        pipe_shift = self.pipe_on_mv - self.pipe_off_mv
        casing_shift = self.casing_on_mv - self.casing_off_mv
        return abs(pipe_shift - casing_shift) <= METALLIC_SHORT_MV


@dataclass(frozen=True)
class CasingAssessment:
    """What a casing test was read as, and why."""

    casing_code: str
    status: CasingStatus
    separation_mv: float
    reason: str
    tested_on: dt.date

    @property
    def due_by(self) -> dt.date | None:
        """When the crossing has to be dealt with, if at all."""
        days = self.status.response_days
        return None if days is None else self.tested_on + dt.timedelta(days=days)


def classify_casing(
    test: CasingTest,
    *,
    short_mv: float = METALLIC_SHORT_MV,
    electrolytic_mv: float = ELECTROLYTIC_MV,
) -> CasingAssessment:
    """Read one casing test as clear, electrolytic or shorted."""
    if short_mv <= 0 or electrolytic_mv <= short_mv:
        raise ValidationError(
            "the electrolytic band has to sit above the short band",
            short_mv=short_mv,
            electrolytic_mv=electrolytic_mv,
        )
    separation = test.separation_mv
    if separation <= short_mv:
        together = test.moves_together
        if together is False:
            return CasingAssessment(
                casing_code=test.casing_code,
                status=CasingStatus.INDETERMINATE,
                separation_mv=separation,
                reason="the readings sit together but the two did not shift together",
                tested_on=test.tested_on,
            )
        return CasingAssessment(
            casing_code=test.casing_code,
            status=CasingStatus.METALLIC_SHORT,
            separation_mv=separation,
            reason="pipe and casing read as one structure",
            tested_on=test.tested_on,
        )
    if separation < electrolytic_mv:
        return CasingAssessment(
            casing_code=test.casing_code,
            status=CasingStatus.ELECTROLYTIC,
            separation_mv=separation,
            reason="the casing is being dragged towards the carrier potential",
            tested_on=test.tested_on,
        )
    return CasingAssessment(
        casing_code=test.casing_code,
        status=CasingStatus.CLEAR,
        separation_mv=separation,
        reason="the casing is sitting on its own",
        tested_on=test.tested_on,
    )
