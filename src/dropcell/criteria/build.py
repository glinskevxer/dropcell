"""Building a criterion set from an operator's settings.

The registry holds the sets this package ships with the figures in the
standards. Those figures are defaults and an operator can move them, so
something has to turn the settings into the same shapes, and doing it at the
point of use means every report builds its own and they drift.

The selection rules do not move. Which criteria apply on a galvanic segment or
in anaerobic ground is a fact about the physics; what the threshold is on a
given day is a decision. Those are separated on purpose, and only the second
one comes from the settings.
"""

from __future__ import annotations

from dropcell.config import Settings
from dropcell.criteria.ac import AcCorrosionLimit, AcToDcRatioLimit, TouchVoltageLimit
from dropcell.criteria.decay import PolarisationDecayCriterion, PolarisationFormationCriterion
from dropcell.criteria.evaluate import CriterionSet
from dropcell.criteria.limits import IrDropShareLimit, OverProtectionLimit
from dropcell.criteria.potential import (
    ANAEROBIC_PROTECTION_MV,
    DEFAULT_PROTECTION_MV,
    OnPotentialCriterion,
    PolarisedPotentialCriterion,
)
from dropcell.criteria.registry import SetSelection, select_set
from dropcell.model.segment import Segment


def anaerobic_threshold(settings: Settings) -> float:
    """The tightened threshold, moved by however far the ordinary one was.

    An operator that works to a criterion a hundred millivolts tighter than the
    standard expects the anaerobic figure to move with it. Leaving the second
    one at its published value produces a policy where the ground that needs
    the most protection gets the least tightening.
    """
    return ANAEROBIC_PROTECTION_MV + (settings.protection_mv - DEFAULT_PROTECTION_MV)


def limits_for(settings: Settings, *, with_ac: bool) -> tuple[object, ...]:
    """The limits an operator's settings imply."""
    ordinary = (OverProtectionLimit(), IrDropShareLimit())
    if not with_ac:
        return ordinary
    return (
        *ordinary,
        AcCorrosionLimit(
            low_risk_a_per_m2=settings.ac_low_risk_a_per_m2,
            high_risk_a_per_m2=settings.ac_high_risk_a_per_m2,
        ),
        AcToDcRatioLimit(),
        TouchVoltageLimit(),
    )


def build_set(
    settings: Settings,
    *,
    name: str,
    anaerobic: bool = False,
    galvanic: bool = False,
    ac_interference: bool = False,
) -> CriterionSet:
    """Build one criterion set from an operator's figures."""
    threshold = anaerobic_threshold(settings) if anaerobic else settings.protection_mv
    criteria: list[object] = [PolarisedPotentialCriterion(threshold_mv=threshold)]
    if galvanic:
        criteria.append(OnPotentialCriterion(threshold_mv=threshold))
    criteria.append(PolarisationDecayCriterion(minimum_decay_mv=settings.decay_mv))
    if not anaerobic and not ac_interference:
        criteria.append(PolarisationFormationCriterion(minimum_shift_mv=settings.decay_mv))
    return CriterionSet(
        name=name,
        criteria=tuple(criteria),  # type: ignore[arg-type]
        limits=limits_for(settings, with_ac=ac_interference),  # type: ignore[arg-type]
        description="built from the settings in force",
    )


def select_for(
    segment: Segment,
    settings: Settings,
    *,
    anaerobic: bool = False,
    ac_interference: bool = False,
) -> SetSelection:
    """Pick the set for a segment and rebuild it at the operator's figures.

    The shipped registry decides which set applies and why. This takes that
    decision and rebuilds the chosen set with the operator's thresholds, so the
    reasons on the selection are the shipped ones and the numbers inside it are
    the local ones.
    """
    chosen = select_set(segment, anaerobic=anaerobic, ac_interference=ac_interference)
    if chosen.name == "unprotected":
        return chosen
    return SetSelection(
        criterion_set=build_set(
            settings,
            name=chosen.name,
            anaerobic=chosen.name == "anaerobic",
            galvanic=chosen.name == "galvanic",
            ac_interference=chosen.name == "ac_interference",
        ),
        reasons=chosen.reasons,
        posts_are_enough=chosen.posts_are_enough,
    )
