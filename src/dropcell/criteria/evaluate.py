"""Putting the criteria and the limits together into one verdict about a point.

The arithmetic is not symmetrical and that is the whole of the difficulty.
Criteria are alternatives, so one pass out of four is a pass. Limits are not,
so one exceedance out of two is a failure no matter how many criteria were met.
A point can therefore be protected and in trouble at the same time, and the
verdict has to carry both facts rather than collapsing them into a word.

There is a third state that neither of those covers. A point where nothing
could be assessed is not protected and is not a corrosion finding either. It is
missing field work, and calling it either of the other two hides the only thing
anybody can act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dropcell.criteria.base import Assessment, Criterion, Evidence, Outcome


@dataclass(frozen=True)
class PointVerdict:
    """What a whole criterion set concluded about one point.

    Criterion results and limit results are held apart on purpose. A limit that
    was not broken reports the same satisfied outcome a criterion does, and if
    the two were pooled then a point with no criterion evidence at all would
    read as protected on the strength of not having been over protected.
    """

    label: str
    criteria: tuple[Assessment, ...] = ()
    limits: tuple[Assessment, ...] = ()

    @property
    def assessments(self) -> tuple[Assessment, ...]:
        """Everything that ran, criteria first."""
        return (*self.criteria, *self.limits)

    @property
    def met(self) -> tuple[Assessment, ...]:
        """Every criterion that was satisfied here."""
        return tuple(item for item in self.criteria if item.outcome is Outcome.MET)

    @property
    def failed(self) -> tuple[Assessment, ...]:
        """Every criterion that ran and was not satisfied."""
        return tuple(item for item in self.criteria if item.outcome is Outcome.NOT_MET)

    @property
    def exceeded(self) -> tuple[Assessment, ...]:
        """Every limit that was broken."""
        return tuple(item for item in self.limits if item.outcome is Outcome.EXCEEDED)

    @property
    def unassessed(self) -> tuple[Assessment, ...]:
        """Every criterion that could not run for want of evidence."""
        return tuple(item for item in self.assessments if item.outcome is Outcome.NOT_ASSESSED)

    @property
    def assessed(self) -> bool:
        """Whether any criterion could be judged here."""
        return any(item.assessed for item in self.criteria)

    @property
    def protected(self) -> bool:
        """Whether some criterion stands as evidence that the pipe is protected."""
        return bool(self.met)

    @property
    def has_findings(self) -> bool:
        """Whether anything here belongs on the exception register."""
        return not self.protected or bool(self.exceeded)

    @property
    def best_margin_mv(self) -> float | None:
        """The largest margin any satisfied criterion had, for ranking."""
        margins = [item.margin_mv for item in self.met if item.margin_mv is not None]
        return max(margins) if margins else None

    @property
    def worst_margin_mv(self) -> float | None:
        """The margin of the criterion that came closest to passing and did not."""
        margins = [item.margin_mv for item in self.failed if item.margin_mv is not None]
        return max(margins) if margins else None

    def by_key(self, key: str) -> Assessment | None:
        """One criterion's assessment, by its key."""
        for item in self.assessments:
            if item.criterion == key:
                return item
        return None

    def summary(self) -> str:
        """One line for a report row."""
        if not self.assessed:
            return f"{self.label}: not assessed"
        parts: list[str] = []
        parts.append("protected" if self.protected else "under criterion")
        if self.exceeded:
            broken = ", ".join(item.criterion for item in self.exceeded)
            parts.append(f"limit exceeded: {broken}")
        return f"{self.label}: " + "; ".join(parts)


@dataclass(frozen=True)
class CriterionSet:
    """The criteria and limits that apply to one kind of segment."""

    name: str
    criteria: tuple[Criterion, ...] = ()
    limits: tuple[Criterion, ...] = ()
    description: str = field(default="", compare=False)

    @property
    def keys(self) -> tuple[str, ...]:
        """Every key in the set, criteria first."""
        return tuple(item.key for item in (*self.criteria, *self.limits))

    def applicable(self, evidence: Evidence) -> tuple[Criterion, ...]:
        """The criteria in this set that are available on this segment."""
        return tuple(item for item in self.criteria if item.applies_to(evidence))

    def evaluate(self, evidence: Evidence) -> PointVerdict:
        """Run every criterion and every limit against one point."""
        judged = [
            criterion.assess(evidence)
            for criterion in self.criteria
            if criterion.applies_to(evidence)
        ]
        bounded = [
            limit.assess(evidence) for limit in self.limits if limit.applies_to(evidence)
        ]
        return PointVerdict(
            label=evidence.label or evidence.segment.code,
            criteria=tuple(judged),
            limits=tuple(bounded),
        )
