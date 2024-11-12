"""Isolation joints, and the way they quietly stop isolating.

An isolating joint is a flange kit or a welded monolithic unit that breaks the
line electrically. It is what keeps our protection current on our own pipe and
off the station steelwork, the foreign line at a tie in, and the earthed
pipework inside a compressor building. Nothing about it moves, so nobody thinks
about it, and it fails by degrees rather than all at once.

The test is the same shape as the casing test and reads the same way. A working
joint shows the two sides at completely different potentials, because they are
two structures. A failed one shows them within a few millivolts of each other,
because they are now one. In between is a joint with something bridging it: a
wet gasket, a bolt that was not sleeved, an instrument cable somebody ran across
it, or a lightning arrester that has failed short.

Where the joint fails, the protection does not simply weaken. Current pours into
whatever is on the other side, the potential on our line collapses over a long
stretch, and the rectifier sits at full output looking healthy.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.model.reading import check_potential
from dropcell.stationing import Station

SHORTED_MV = 15.0
PARTIAL_MV = 100.0


class JointKind(StrEnum):
    """How the break in the line is made."""

    FLANGE_KIT = "flange_kit"
    MONOLITHIC = "monolithic"
    ISOLATING_UNION = "isolating_union"

    @property
    def is_serviceable(self) -> bool:
        """Whether a failed joint can be repaired rather than cut out.

        A flange kit is bolts and gaskets and can be rebuilt in a day. A
        monolithic joint is welded into the line and replacing it is a cut out,
        so a failed one usually gets a bond and a rethink instead of a repair.
        """
        return self is not JointKind.MONOLITHIC


class IsolationStatus(StrEnum):
    """What an isolation test concluded."""

    ISOLATING = "isolating"
    PARTIAL = "partial"
    SHORTED = "shorted"

    @property
    def needs_work(self) -> bool:
        """Whether somebody has to go and look at it."""
        return self is not IsolationStatus.ISOLATING

    @property
    def response_days(self) -> int | None:
        """How long there is before it has to be dealt with."""
        return _RESPONSE_DAYS[self]


_RESPONSE_DAYS: dict[IsolationStatus, int | None] = {
    IsolationStatus.ISOLATING: None,
    IsolationStatus.PARTIAL: 180,
    IsolationStatus.SHORTED: 45,
}


@dataclass(frozen=True)
class IsolationJoint:
    """One electrical break in the line."""

    code: str
    line_code: str
    station: Station
    kind: JointKind
    separates: str
    installed_on: dt.date
    surge_protector_fitted: bool = False
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="joint code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if not self.separates.strip():
            raise ValidationError("a joint has to separate us from something", code=self.code)
        object.__setattr__(self, "separates", self.separates.strip())


@dataclass(frozen=True)
class IsolationTest:
    """One visit to an isolating joint."""

    joint_code: str
    tested_on: dt.date
    our_side_mv: float
    other_side_mv: float
    surge_protector_removed: bool = False
    technician: str = ""
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "joint_code", normalise_code(self.joint_code, kind="joint code")
        )
        check_potential(self.our_side_mv, "our side potential")
        check_potential(self.other_side_mv, "other side potential")

    @property
    def separation_mv(self) -> float:
        """How far apart the two sides sit."""
        return abs(self.our_side_mv - self.other_side_mv)


@dataclass(frozen=True)
class IsolationAssessment:
    """What an isolation test was read as."""

    joint_code: str
    status: IsolationStatus
    separation_mv: float
    reason: str
    tested_on: dt.date

    @property
    def due_by(self) -> dt.date | None:
        """When it has to be dealt with, if at all."""
        days = self.status.response_days
        return None if days is None else self.tested_on + dt.timedelta(days=days)


def classify_isolation(
    test: IsolationTest,
    joint: IsolationJoint | None = None,
    *,
    shorted_mv: float = SHORTED_MV,
    partial_mv: float = PARTIAL_MV,
) -> IsolationAssessment:
    """Read one isolation test.

    A joint with a surge protector across it will read shorted while the
    protector is in place, because that is what a surge protector does at DC on
    some designs. A test taken without lifting it says nothing, and reporting it
    as a failure sends a crew to rebuild a joint that was working.
    """
    if shorted_mv <= 0 or partial_mv <= shorted_mv:
        raise ValidationError(
            "the partial band has to sit above the shorted band",
            shorted_mv=shorted_mv,
            partial_mv=partial_mv,
        )
    separation = test.separation_mv
    fitted = joint is not None and joint.surge_protector_fitted
    if separation <= shorted_mv and fitted and not test.surge_protector_removed:
        return IsolationAssessment(
            joint_code=test.joint_code,
            status=IsolationStatus.PARTIAL,
            separation_mv=separation,
            reason="read with the surge protector still across it, so it proves nothing",
            tested_on=test.tested_on,
        )
    if separation <= shorted_mv:
        return IsolationAssessment(
            joint_code=test.joint_code,
            status=IsolationStatus.SHORTED,
            separation_mv=separation,
            reason="both sides read as one structure",
            tested_on=test.tested_on,
        )
    if separation < partial_mv:
        return IsolationAssessment(
            joint_code=test.joint_code,
            status=IsolationStatus.PARTIAL,
            separation_mv=separation,
            reason="something is bridging the joint",
            tested_on=test.tested_on,
        )
    return IsolationAssessment(
        joint_code=test.joint_code,
        status=IsolationStatus.ISOLATING,
        separation_mv=separation,
        reason="the two sides are at their own potentials",
        tested_on=test.tested_on,
    )
