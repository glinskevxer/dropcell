"""Which criteria apply to which segment, and why.

Choosing a criterion set is a decision with consequences, so it is written down
here rather than made at the point of use. Two rules do most of the work and
they interact.

The protection method decides what can be measured at all. An impressed current
segment can be interrupted, so the on potential is not accepted as evidence.
A galvanic segment cannot be, so it is.

The soil decides how hard the threshold is. Ground carrying sulfate reducing
bacteria needs the tighter figure, and that changes what the polarised
criterion means without changing which criteria are in the set.

The coating decides nothing about the criteria and everything about whether
readings at posts are enough evidence to apply them to the pipe in between.
That is a separate answer and it is returned separately.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.criteria.ac import AcCorrosionLimit, AcToDcRatioLimit, TouchVoltageLimit
from dropcell.criteria.decay import PolarisationDecayCriterion, PolarisationFormationCriterion
from dropcell.criteria.evaluate import CriterionSet
from dropcell.criteria.limits import IrDropShareLimit, OverProtectionLimit
from dropcell.criteria.potential import (
    ANAEROBIC_PROTECTION_MV,
    OnPotentialCriterion,
    PolarisedPotentialCriterion,
)
from dropcell.errors import PolicyError
from dropcell.model.enums import ProtectionMethod
from dropcell.model.segment import Segment

STANDARD_LIMITS = (OverProtectionLimit(), IrDropShareLimit())
AC_LIMITS = (AcCorrosionLimit(), AcToDcRatioLimit(), TouchVoltageLimit())

IMPRESSED_CURRENT = CriterionSet(
    name="impressed_current",
    criteria=(
        PolarisedPotentialCriterion(),
        PolarisationDecayCriterion(),
        PolarisationFormationCriterion(),
    ),
    limits=STANDARD_LIMITS,
    description="the ordinary set for a segment fed by a rectifier",
)

GALVANIC = CriterionSet(
    name="galvanic",
    criteria=(
        PolarisedPotentialCriterion(),
        OnPotentialCriterion(),
        PolarisationDecayCriterion(),
    ),
    limits=STANDARD_LIMITS,
    description="anodes bonded to the pipe, where the on potential is admissible",
)

ANAEROBIC = CriterionSet(
    name="anaerobic",
    criteria=(
        PolarisedPotentialCriterion(threshold_mv=ANAEROBIC_PROTECTION_MV),
        PolarisationDecayCriterion(),
    ),
    limits=STANDARD_LIMITS,
    description="the tightened threshold for soil with sulfate reducing bacteria",
)

AC_INTERFERENCE = CriterionSet(
    name="ac_interference",
    criteria=(PolarisedPotentialCriterion(), PolarisationDecayCriterion()),
    limits=(*STANDARD_LIMITS, *AC_LIMITS),
    description="the ordinary set with the AC limits added",
)

UNPROTECTED = CriterionSet(
    name="unprotected",
    criteria=(),
    limits=(),
    description="pipe with no protection on it, where no criterion applies",
)

SETS: dict[str, CriterionSet] = {
    item.name: item
    for item in (IMPRESSED_CURRENT, GALVANIC, ANAEROBIC, AC_INTERFERENCE, UNPROTECTED)
}


def get_set(name: str) -> CriterionSet:
    """Look a set up by name, refusing one that is not defined."""
    try:
        return SETS[name]
    except KeyError:
        raise PolicyError(
            "no criterion set by that name", name=name, known=sorted(SETS)
        ) from None


@dataclass(frozen=True)
class SetSelection:
    """The set chosen for a segment, with the reasons it was chosen."""

    criterion_set: CriterionSet
    reasons: tuple[str, ...]
    posts_are_enough: bool

    @property
    def name(self) -> str:
        """The chosen set's name."""
        return self.criterion_set.name


def select_set(
    segment: Segment,
    *,
    anaerobic: bool = False,
    ac_interference: bool = False,
) -> SetSelection:
    """Pick the criterion set a segment should be judged against.

    The AC set wins over the anaerobic one where both apply, because the AC
    limits are the ones that catch a failure the potential criteria cannot see
    at all. Losing a tighter threshold is a smaller loss than losing a whole
    mechanism.
    """
    reasons: list[str] = []
    if segment.protection is ProtectionMethod.UNPROTECTED:
        return SetSelection(
            criterion_set=UNPROTECTED,
            reasons=("segment carries no protection",),
            posts_are_enough=False,
        )
    if ac_interference:
        chosen = AC_INTERFERENCE
        reasons.append("AC interference is present on this segment")
    elif anaerobic:
        chosen = ANAEROBIC
        reasons.append("soil carries sulfate reducing bacteria")
    elif segment.protection is ProtectionMethod.GALVANIC:
        chosen = GALVANIC
        reasons.append("anodes are bonded directly and cannot be interrupted")
    else:
        chosen = IMPRESSED_CURRENT
        reasons.append("segment is fed by a rectifier")
    if anaerobic and chosen is not ANAEROBIC:
        reasons.append("anaerobic soil noted but the AC set was taken instead")
    posts_are_enough = not segment.needs_above_ground_survey
    if not posts_are_enough:
        reasons.append("coating can shield, so readings at posts do not cover the pipe between")
    return SetSelection(
        criterion_set=chosen,
        reasons=tuple(reasons),
        posts_are_enough=posts_are_enough,
    )
