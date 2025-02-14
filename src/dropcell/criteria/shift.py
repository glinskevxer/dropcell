"""The negative shift criterion, which is the one everybody still argues about.

Three hundred millivolts of shift from the native potential once counted as
protection on its own, and a great deal of old pipe was signed off against it.
It was withdrawn from the standards because the shift can be produced without
protecting anything: a big enough current will move the potential of a
structure that is still corroding, and on bare pipe in low resistivity ground
that is exactly what happens.

It is here for two reasons and neither of them is that it is a good criterion.
Historical records were made against it and a register that cannot express what
a 1978 survey concluded cannot hold that survey at all. And it is still the
quickest way to see that a newly energised system is doing something, which is
a different question from whether it is doing enough.

So it never returns a satisfied outcome on its own terms. It reports what the
shift was and says explicitly that a shift is not evidence of protection, which
is the whole of what was wrong with it in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.criteria.base import Assessment, Criterion, Evidence, Outcome, not_assessed
from dropcell.model.enums import CoatingType, ProtectionMethod

HISTORIC_SHIFT_MV = 300.0


@dataclass(frozen=True)
class NegativeShiftIndicator(Criterion):
    """Shift from the native potential, reported and never accepted."""

    minimum_shift_mv: float = HISTORIC_SHIFT_MV
    key: str = "negative_shift"
    label: str = "shift from the native potential, historical only"

    def applies_to(self, evidence: Evidence) -> bool:
        """Needs a native potential and a protected one to compare it with."""
        return (
            evidence.native_mv is not None
            and evidence.protection is not ProtectionMethod.UNPROTECTED
            and (evidence.on_mv is not None or evidence.off_mv is not None)
        )

    def assess(self, evidence: Evidence) -> Assessment:
        """Report the shift, and refuse to call it protection."""
        if evidence.native_mv is None:
            return not_assessed(self.key, ["native_mv"])
        protected = evidence.off_mv if evidence.off_mv is not None else evidence.on_mv
        if protected is None:
            return not_assessed(self.key, ["off_mv", "on_mv"])
        shift = evidence.native_mv - protected
        reached = shift >= self.minimum_shift_mv
        note = (
            "a shift is not evidence of protection and this criterion was withdrawn"
            if reached
            else "not even the withdrawn shift was reached"
        )
        return Assessment(
            criterion=self.key,
            outcome=Outcome.NOT_MET,
            margin_mv=shift - self.minimum_shift_mv,
            note=note,
            detail={
                "shift_mv": shift,
                "native_mv": evidence.native_mv,
                "protected_mv": protected,
                "minimum_shift_mv": self.minimum_shift_mv,
                "reached": reached,
                "withdrawn": True,
            },
        )


def shift_is_suspect(evidence: Evidence, shift_mv: float) -> bool:
    """Whether a shift this large on this pipe should be believed at all.

    Bare pipe in low resistivity ground will show a large shift under a current
    that is nowhere near enough to protect it, because there is so much steel
    exposed that the potential moves before the polarisation does. That is the
    case the criterion was withdrawn over, and it is worth naming when it is in
    front of you.
    """
    if shift_mv < HISTORIC_SHIFT_MV:
        return False
    if evidence.coating is not CoatingType.BARE:
        return False
    resistivity = evidence.soil_resistivity_ohm_m or evidence.segment.soil_resistivity_ohm_m
    return resistivity is not None and resistivity < 20.0
