"""Limits, which are the rules that hold whichever criterion was used.

A criterion is an alternative: meet any one of them and the pipe is protected.
A limit is not. It applies to every point regardless of which criterion that
point passed, and a point can pass a criterion and break a limit at the same
time. Too much protection is a real failure mode and it looks like a very good
reading, which is exactly why it needs a rule of its own rather than a footnote
on the criteria.

Two things go wrong at very negative potentials. Hydrogen comes off the steel
and gets under the coating, lifting it away in blisters, and on higher strength
steel some of that hydrogen goes into the metal and embrittles it. Coatings that
were already prone to disbonding come off sooner, so the limit is not one
number for every pipe.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.criteria.base import Assessment, Criterion, Evidence, Outcome, not_assessed
from dropcell.model.enums import CoatingType

DISBONDMENT_LIMIT_MV = -1200.0
SHIELDING_COATING_LIMIT_MV = -1100.0
IR_DROP_SHARE_LIMIT = 0.35


def disbondment_limit_mv(coating: CoatingType) -> float:
    """The most negative potential this coating should be held at."""
    if coating.shields_current:
        return SHIELDING_COATING_LIMIT_MV
    return DISBONDMENT_LIMIT_MV


@dataclass(frozen=True)
class OverProtectionLimit(Criterion):
    """A ceiling on how negative the polarised potential is allowed to get."""

    key: str = "over_protection"
    label: str = "polarised potential against the disbondment limit"

    def applies_to(self, evidence: Evidence) -> bool:
        """Every point with a polarised potential is subject to it."""
        return evidence.off_mv is not None

    def limit_for(self, evidence: Evidence) -> float:
        """The limit that applies on this segment's coating."""
        return disbondment_limit_mv(evidence.coating)

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge one point against the disbondment limit."""
        missing = evidence.missing("off_mv")
        if missing:
            return not_assessed(self.key, missing)
        off_mv = evidence.off_mv
        assert off_mv is not None
        limit = self.limit_for(evidence)
        exceeded = off_mv < limit
        return Assessment(
            criterion=self.key,
            outcome=Outcome.EXCEEDED if exceeded else Outcome.MET,
            margin_mv=off_mv - limit,
            note="held more negative than the coating will take" if exceeded else "",
            detail={
                "off_mv": off_mv,
                "limit_mv": limit,
                "coating": str(evidence.coating),
            },
        )


@dataclass(frozen=True)
class IrDropShareLimit(Criterion):
    """A ceiling on how much of the on potential is soil drop rather than pipe.

    When most of what the meter reads is voltage in the ground, the on potential
    has stopped describing the pipe at all. That happens beside a groundbed, in
    dry rock, and anywhere a rectifier is being driven hard to reach one bad
    stretch. It is not itself a corrosion problem, but it means the on readings
    for that stretch cannot be used for anything and the survey has to be redone
    with interruption.
    """

    share_limit: float = IR_DROP_SHARE_LIMIT
    key: str = "ir_drop_share"
    label: str = "IR drop as a share of the on potential"

    def applies_to(self, evidence: Evidence) -> bool:
        """Needs both potentials to be able to say anything."""
        return evidence.on_mv is not None and evidence.off_mv is not None

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge how much of the on reading was soil."""
        missing = evidence.missing("on_mv", "off_mv")
        if missing:
            return not_assessed(self.key, missing)
        on_mv = evidence.on_mv
        off_mv = evidence.off_mv
        assert on_mv is not None
        assert off_mv is not None
        if on_mv == 0:
            return not_assessed(self.key, ["on_mv"])
        share = abs(on_mv - off_mv) / abs(on_mv)
        exceeded = share > self.share_limit
        return Assessment(
            criterion=self.key,
            outcome=Outcome.EXCEEDED if exceeded else Outcome.MET,
            margin_mv=None,
            note="most of the on reading is soil drop" if exceeded else "",
            detail={
                "ir_drop_mv": on_mv - off_mv,
                "share": share,
                "share_limit": self.share_limit,
            },
        )
