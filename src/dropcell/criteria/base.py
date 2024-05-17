"""What a protection criterion is, and what it is allowed to say.

There is no single test for whether cathodic protection is working. There is a
short list of criteria, any one of which is accepted as evidence, and a set of
limits that hold no matter which criterion was used. A criterion takes the
evidence gathered at a point and returns one verdict about that point.

Two things a criterion must not do. It must not go and fetch anything: if the
evidence it needs is not in front of it, the honest answer is that the point was
not assessed, and inventing a default would turn missing field work into a pass.
And it must not decide what the segment as a whole is doing, because that
depends on the other criteria and on the limits, which is somebody else's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from dropcell.model.enums import CoatingType, ProtectionMethod
from dropcell.model.segment import Segment


class Outcome(StrEnum):
    """What one criterion concluded."""

    MET = "met"
    NOT_MET = "not_met"
    EXCEEDED = "exceeded"
    NOT_ASSESSED = "not_assessed"

    @property
    def is_evidence_of_protection(self) -> bool:
        """Whether this outcome can stand as proof the pipe is protected."""
        return self is Outcome.MET

    @property
    def is_a_finding(self) -> bool:
        """Whether this outcome puts something on the exception register."""
        return self in {Outcome.NOT_MET, Outcome.EXCEEDED}


@dataclass(frozen=True)
class Evidence:
    """Everything a criterion might be handed about one point on the line.

    Every measurement is optional because field work is. A post with a snapped
    lead wire, a galvanic segment that cannot be interrupted and a coupon that
    was never installed all produce evidence with holes in it, and the criteria
    have to say so rather than guess.
    """

    segment: Segment
    on_mv: float | None = None
    off_mv: float | None = None
    native_mv: float | None = None
    depolarised_mv: float | None = None
    ac_voltage_v: float | None = None
    ac_current_density_a_per_m2: float | None = None
    dc_current_density_a_per_m2: float | None = None
    depolarised_after_hours: float | None = None
    soil_resistivity_ohm_m: float | None = None
    interrupted: bool = False
    dissimilar_metals: bool = False
    stray_current_suspected: bool = False
    label: str = ""

    @property
    def coating(self) -> CoatingType:
        """The coating of the segment this point sits on."""
        return self.segment.coating

    @property
    def protection(self) -> ProtectionMethod:
        """How the segment this point sits on is fed current."""
        return self.segment.protection

    def missing(self, *names: str) -> list[str]:
        """Which of the named measurements are not present."""
        return [name for name in names if getattr(self, name) is None]


@dataclass(frozen=True)
class Assessment:
    """One criterion's verdict about one point."""

    criterion: str
    outcome: Outcome
    margin_mv: float | None = None
    note: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def met(self) -> bool:
        """Whether the criterion was satisfied here."""
        return self.outcome is Outcome.MET

    @property
    def assessed(self) -> bool:
        """Whether there was enough evidence to say anything at all."""
        return self.outcome is not Outcome.NOT_ASSESSED

    def as_dict(self) -> dict[str, Any]:
        """Flatten for a report row or a stored result."""
        return {
            "criterion": self.criterion,
            "outcome": str(self.outcome),
            "margin_mv": self.margin_mv,
            "note": self.note,
            **self.detail,
        }


@runtime_checkable
class Criterion(Protocol):
    """The shape every criterion has."""

    key: str
    label: str

    def applies_to(self, evidence: Evidence) -> bool:
        """Whether this criterion is one of the ones available on this segment."""
        ...

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge one point."""
        ...


def not_assessed(key: str, missing: list[str]) -> Assessment:
    """The verdict a criterion returns when the field work it needs is absent."""
    return Assessment(
        criterion=key,
        outcome=Outcome.NOT_ASSESSED,
        note="missing " + ", ".join(missing) if missing else "no evidence",
        detail={"missing": missing},
    )
