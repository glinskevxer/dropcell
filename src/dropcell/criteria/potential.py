"""The two potential criteria, and why only one of them is usually allowed.

The polarised criterion is the honest one. Interrupt every current source at
once, read the potential in the moment before polarisation starts to decay, and
compare it with the threshold. What is left is the potential the steel actually
sits at, with the voltage drop through the soil taken out.

The on potential criterion compares the same threshold against the reading with
everything still running. That number includes the IR drop, so it is always
more negative than the truth and it always flatters the line. It is accepted
only where interruption is not possible, which in practice means galvanic
anodes bonded directly to the pipe.

The threshold itself moves. In soil carrying sulfate reducing bacteria the
usual figure is not enough, because the bacteria go on working at potentials
that would stop ordinary corrosion, and the criterion tightens by a hundred
millivolts.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.criteria.base import Assessment, Criterion, Evidence, Outcome, not_assessed
from dropcell.model.enums import ProtectionMethod

DEFAULT_PROTECTION_MV = -850.0
ANAEROBIC_PROTECTION_MV = -950.0


@dataclass(frozen=True)
class PolarisedPotentialCriterion(Criterion):
    """Instant off potential against a threshold."""

    threshold_mv: float = DEFAULT_PROTECTION_MV
    key: str = "polarised_potential"
    label: str = "polarised potential against the threshold"

    def applies_to(self, evidence: Evidence) -> bool:
        """Anything with a current source on it can be judged this way."""
        return evidence.protection is not ProtectionMethod.UNPROTECTED

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge one point on its instant off potential."""
        missing = evidence.missing("off_mv")
        if missing:
            return not_assessed(self.key, missing)
        off_mv = evidence.off_mv
        assert off_mv is not None
        margin = self.threshold_mv - off_mv
        return Assessment(
            criterion=self.key,
            outcome=Outcome.MET if off_mv <= self.threshold_mv else Outcome.NOT_MET,
            margin_mv=margin,
            note="" if margin >= 0 else "short of the threshold",
            detail={"off_mv": off_mv, "threshold_mv": self.threshold_mv},
        )


@dataclass(frozen=True)
class OnPotentialCriterion(Criterion):
    """On potential against a threshold, allowed only where interruption is not.

    The reading includes whatever IR drop the soil puts in the measuring
    circuit, so a pass here is weaker evidence than a pass on the polarised
    criterion. It is refused outright on an impressed current segment, where
    interrupting the rectifiers is a morning's work rather than an impossibility.
    """

    threshold_mv: float = DEFAULT_PROTECTION_MV
    key: str = "on_potential"
    label: str = "on potential against the threshold"

    def applies_to(self, evidence: Evidence) -> bool:
        """Only where the current cannot be switched off."""
        return evidence.protection is ProtectionMethod.GALVANIC

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge one point on its on potential."""
        if not self.applies_to(evidence):
            return Assessment(
                criterion=self.key,
                outcome=Outcome.NOT_ASSESSED,
                note="this segment can be interrupted, so the on potential is not evidence",
                detail={"protection": str(evidence.protection)},
            )
        missing = evidence.missing("on_mv")
        if missing:
            return not_assessed(self.key, missing)
        on_mv = evidence.on_mv
        assert on_mv is not None
        margin = self.threshold_mv - on_mv
        return Assessment(
            criterion=self.key,
            outcome=Outcome.MET if on_mv <= self.threshold_mv else Outcome.NOT_MET,
            margin_mv=margin,
            note="includes IR drop",
            detail={"on_mv": on_mv, "threshold_mv": self.threshold_mv},
        )


def anaerobic_polarised_criterion() -> PolarisedPotentialCriterion:
    """The tightened criterion for soil with sulfate reducing bacteria in it."""
    return PolarisedPotentialCriterion(threshold_mv=ANAEROBIC_PROTECTION_MV)
