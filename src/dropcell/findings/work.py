"""Work orders, which are the other half of a finding.

A finding says something is wrong. A work order says somebody is going to do
something about it, on a date, for a price, and it exists separately because the
two do not line up one to one. One excavation deals with three defects that
happen to be within twenty metres of each other. One finding sometimes needs a
survey, then a dig, then a re-read, and those are three jobs with three dates.

So a work order carries a set of finding codes rather than one, and closing an
order does not close the findings on it. Whoever did the work decides what got
fixed, and a crew that dug three holes and found two of the three defects has to
be able to say so.

The estimate is kept beside the actual because the gap between them is the only
number a CP budget is ever argued from, and it is lost the moment somebody
overwrites the estimate with what it cost.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code


class WorkKind(StrEnum):
    """What sort of job it is."""

    EXCAVATION = "excavation"
    ANODE_INSTALL = "anode_install"
    BOND_INSTALL = "bond_install"
    RECTIFIER_REPAIR = "rectifier_repair"
    GROUNDBED_REPLACE = "groundbed_replace"
    CASING_REPAIR = "casing_repair"
    JOINT_REPAIR = "joint_repair"
    SURVEY = "survey"

    @property
    def breaks_ground(self) -> bool:
        """Whether the job needs an excavation permit and a service search."""
        return self in {
            WorkKind.EXCAVATION,
            WorkKind.ANODE_INSTALL,
            WorkKind.GROUNDBED_REPLACE,
            WorkKind.CASING_REPAIR,
        }

    @property
    def needs_reread(self) -> bool:
        """Whether the job has to be followed by a reading to prove it worked.

        A survey produces its own evidence. Everything else changes the system
        and is not finished until somebody has read a post and seen the change,
        which is why a completed order does not on its own clear a finding.
        """
        return self is not WorkKind.SURVEY


class WorkState(StrEnum):
    """Where a job has got to."""

    DRAFT = "draft"
    ISSUED = "issued"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"

    @property
    def is_closed(self) -> bool:
        """Whether the job is off the live list."""
        return self in {WorkState.DONE, WorkState.CANCELLED}


ALLOWED_WORK_TRANSITIONS: dict[WorkState, frozenset[WorkState]] = {
    WorkState.DRAFT: frozenset({WorkState.ISSUED, WorkState.CANCELLED}),
    WorkState.ISSUED: frozenset(
        {WorkState.IN_PROGRESS, WorkState.DONE, WorkState.CANCELLED, WorkState.DRAFT}
    ),
    WorkState.IN_PROGRESS: frozenset({WorkState.DONE, WorkState.CANCELLED}),
    WorkState.DONE: frozenset(),
    WorkState.CANCELLED: frozenset({WorkState.DRAFT}),
}


@dataclass(frozen=True)
class WorkOrder:
    """One job."""

    code: str
    line_code: str
    kind: WorkKind
    raised_on: dt.date
    finding_codes: tuple[str, ...]
    summary: str
    state: WorkState = WorkState.DRAFT
    planned_for: dt.date | None = None
    completed_on: dt.date | None = None
    contractor: str = ""
    estimate: float | None = None
    actual: float | None = None
    notes: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="work order code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        object.__setattr__(
            self,
            "finding_codes",
            tuple(
                sorted(
                    {normalise_code(code, kind="finding code") for code in self.finding_codes}
                )
            ),
        )
        if not self.summary.strip():
            raise ValidationError("a work order needs a summary", code=self.code)
        object.__setattr__(self, "summary", self.summary.strip())
        for label, value in (("estimate", self.estimate), ("actual", self.actual)):
            if value is not None and value < 0:
                raise ValidationError(f"{label} cannot be negative", code=self.code)
        if self.planned_for is not None and self.planned_for < self.raised_on:
            raise ValidationError(
                "a job cannot be planned before it was raised", code=self.code
            )
        if self.state is WorkState.DONE:
            if self.completed_on is None:
                raise ValidationError("a finished job needs a date", code=self.code)
            if self.completed_on < self.raised_on:
                raise ValidationError(
                    "a job cannot finish before it was raised", code=self.code
                )
        elif self.completed_on is not None:
            raise ValidationError(
                "only a finished job carries a completion date", code=self.code
            )

    @property
    def is_open(self) -> bool:
        """Whether the job is still live."""
        return not self.state.is_closed

    @property
    def findings(self) -> int:
        """How many findings this job is against."""
        return len(self.finding_codes)

    @property
    def variance(self) -> float | None:
        """What it cost against what it was going to cost."""
        if self.estimate is None or self.actual is None:
            return None
        return self.actual - self.estimate

    def covers(self, finding_code: str) -> bool:
        """Whether a finding is on this job."""
        return normalise_code(finding_code, kind="finding code") in self.finding_codes

    def can_move_to(self, state: WorkState) -> bool:
        """Whether a transition to that state is allowed from here."""
        return state in ALLOWED_WORK_TRANSITIONS[self.state]
