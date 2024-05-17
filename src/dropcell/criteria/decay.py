"""The decay criterion, which measures the protection rather than the potential.

Switch everything off and leave it off. The pipe drifts back towards the
potential it would have had with no protection at all, and how far it drifts is
how much polarisation the system had built up. A hundred millivolts of drift is
accepted as evidence that protection is working, whatever the absolute numbers
were.

It is the criterion for pipe that will never reach the usual threshold, which
is most old bare pipe and anything in very high resistivity ground. It is also
the criterion that is easiest to misuse. A decay reading taken twenty minutes
after switch off measures the tail of the IR drop and not polarisation at all,
so the reading has to sit for hours. And where a second metal is bonded to the
pipe, or stray current is coming and going on its own schedule, the drift
measures that instead and the criterion says nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.criteria.base import Assessment, Criterion, Evidence, Outcome, not_assessed
from dropcell.model.enums import ProtectionMethod

MINIMUM_DECAY_MV = 100.0
MINIMUM_DEPOLARISATION_HOURS = 2.0


@dataclass(frozen=True)
class PolarisationDecayCriterion(Criterion):
    """A hundred millivolts of drift after the current is switched off."""

    minimum_decay_mv: float = MINIMUM_DECAY_MV
    minimum_hours: float = MINIMUM_DEPOLARISATION_HOURS
    key: str = "polarisation_decay"
    label: str = "polarisation decay after switch off"

    def applies_to(self, evidence: Evidence) -> bool:
        """Refused where something else on the circuit would move the reading."""
        if evidence.protection is ProtectionMethod.UNPROTECTED:
            return False
        return not (evidence.dissimilar_metals or evidence.stray_current_suspected)

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge one point on how far it depolarised."""
        if evidence.dissimilar_metals or evidence.stray_current_suspected:
            return Assessment(
                criterion=self.key,
                outcome=Outcome.NOT_ASSESSED,
                note="decay is not evidence with dissimilar metals or stray current present",
                detail={
                    "dissimilar_metals": evidence.dissimilar_metals,
                    "stray_current_suspected": evidence.stray_current_suspected,
                },
            )
        missing = evidence.missing("off_mv", "depolarised_mv")
        if missing:
            return not_assessed(self.key, missing)
        hours = evidence.depolarised_after_hours
        if hours is not None and hours < self.minimum_hours:
            return Assessment(
                criterion=self.key,
                outcome=Outcome.NOT_ASSESSED,
                note="the pipe was not left off long enough for this to be decay",
                detail={"hours": hours, "minimum_hours": self.minimum_hours},
            )
        off_mv = evidence.off_mv
        depolarised_mv = evidence.depolarised_mv
        assert off_mv is not None
        assert depolarised_mv is not None
        decay = depolarised_mv - off_mv
        return Assessment(
            criterion=self.key,
            outcome=Outcome.MET if decay >= self.minimum_decay_mv else Outcome.NOT_MET,
            margin_mv=decay - self.minimum_decay_mv,
            note="" if decay >= self.minimum_decay_mv else "not enough decay",
            detail={
                "decay_mv": decay,
                "off_mv": off_mv,
                "depolarised_mv": depolarised_mv,
                "minimum_decay_mv": self.minimum_decay_mv,
            },
        )


@dataclass(frozen=True)
class PolarisationFormationCriterion(Criterion):
    """The same hundred millivolts, measured as it builds rather than as it decays.

    A new system is switched on over pipe whose native potential is known, and
    the shift from that native potential is watched instead. It answers the same
    question as decay and it does not need the line taken out of protection to
    do it, but it only works where somebody wrote the native potentials down
    before the rectifiers were ever energised.
    """

    minimum_shift_mv: float = MINIMUM_DECAY_MV
    key: str = "polarisation_formation"
    label: str = "polarisation shift from the native potential"

    def applies_to(self, evidence: Evidence) -> bool:
        """Needs a native potential from before the system was energised."""
        return evidence.native_mv is not None

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge one point on how far it moved from its native potential."""
        missing = evidence.missing("native_mv", "off_mv")
        if missing:
            return not_assessed(self.key, missing)
        native_mv = evidence.native_mv
        off_mv = evidence.off_mv
        assert native_mv is not None
        assert off_mv is not None
        shift = native_mv - off_mv
        return Assessment(
            criterion=self.key,
            outcome=Outcome.MET if shift >= self.minimum_shift_mv else Outcome.NOT_MET,
            margin_mv=shift - self.minimum_shift_mv,
            note="" if shift >= self.minimum_shift_mv else "not enough shift",
            detail={
                "shift_mv": shift,
                "native_mv": native_mv,
                "off_mv": off_mv,
                "minimum_shift_mv": self.minimum_shift_mv,
            },
        )
