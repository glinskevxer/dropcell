"""The exception register, which is the only part of this anybody acts on.

Everything else in dropcell produces a number. A finding is a number that
somebody now owns. It has a place on the line, a date it was raised, a reason
it was raised, a date by which something has to happen, and a state that only
moves in the directions a state is allowed to move in.

The states are deliberately few. Open means nobody has done anything yet.
Scheduled means work exists and has a date. Cleared means the condition was
fixed and a follow up reading proved it. Accepted means somebody with authority
decided to live with it, and that decision carries a name and a reason because
it is the one state that closes a finding without fixing anything.

Reopening is allowed from cleared, because a repair that did not hold is the
same finding coming back rather than a new one, and losing that history loses
the fact that this spot has failed twice.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station, StationRange


class FindingKind(StrEnum):
    """What sort of exception was raised."""

    UNDER_CRITERION = "under_criterion"
    OVER_PROTECTED = "over_protected"
    COATING_DEFECT = "coating_defect"
    SHORTED_CASING = "shorted_casing"
    INTERFERENCE = "interference"
    AC_CORROSION = "ac_corrosion"
    BOND_FAULT = "bond_fault"
    RECTIFIER_FAULT = "rectifier_fault"
    GROUNDBED_DEPLETION = "groundbed_depletion"
    MISSING_SURVEY = "missing_survey"

    @property
    def is_measurement_gap(self) -> bool:
        """Whether this is missing work rather than a condition on the pipe."""
        return self is FindingKind.MISSING_SURVEY


class FindingState(StrEnum):
    """Where a finding has got to."""

    OPEN = "open"
    SCHEDULED = "scheduled"
    CLEARED = "cleared"
    ACCEPTED = "accepted"

    @property
    def is_closed(self) -> bool:
        """Whether the finding is off the live register."""
        return self in {FindingState.CLEARED, FindingState.ACCEPTED}


ALLOWED_TRANSITIONS: dict[FindingState, frozenset[FindingState]] = {
    FindingState.OPEN: frozenset(
        {FindingState.SCHEDULED, FindingState.CLEARED, FindingState.ACCEPTED}
    ),
    FindingState.SCHEDULED: frozenset(
        {FindingState.OPEN, FindingState.CLEARED, FindingState.ACCEPTED}
    ),
    FindingState.CLEARED: frozenset({FindingState.OPEN}),
    FindingState.ACCEPTED: frozenset({FindingState.OPEN}),
}


@dataclass(frozen=True)
class Finding:
    """One exception against one place on the line."""

    code: str
    line_code: str
    kind: FindingKind
    raised_on: dt.date
    extent: StationRange
    summary: str
    state: FindingState = FindingState.OPEN
    due_by: dt.date | None = None
    closed_on: dt.date | None = None
    closed_by: str = ""
    closed_reason: str = ""
    source: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="finding code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if not self.summary.strip():
            raise ValidationError("a finding needs a summary", code=self.code)
        object.__setattr__(self, "summary", self.summary.strip())
        if self.due_by is not None and self.due_by < self.raised_on:
            raise ValidationError(
                "a finding cannot be due before it was raised",
                code=self.code,
                raised_on=self.raised_on.isoformat(),
                due_by=self.due_by.isoformat(),
            )
        if self.state.is_closed:
            if self.closed_on is None:
                raise ValidationError("a closed finding needs a date", code=self.code)
            if self.closed_on < self.raised_on:
                raise ValidationError(
                    "a finding cannot close before it was raised", code=self.code
                )
        elif self.closed_on is not None:
            raise ValidationError("an open finding cannot carry a closing date", code=self.code)
        if self.state is FindingState.ACCEPTED and not self.closed_reason.strip():
            raise ValidationError(
                "accepting a finding without fixing it needs a reason", code=self.code
            )

    @property
    def station(self) -> Station:
        """Where the finding starts, for a report that wants one number."""
        return self.extent.start

    @property
    def length_m(self) -> float:
        """How much pipe the finding covers."""
        return self.extent.length_m

    @property
    def is_open(self) -> bool:
        """Whether the finding is still on the live register."""
        return not self.state.is_closed

    def is_overdue(self, as_of: dt.date) -> bool:
        """Whether it is past its date and still open."""
        return self.is_open and self.due_by is not None and as_of > self.due_by

    def age_days(self, as_of: dt.date) -> int:
        """How long the finding has been on the register."""
        end = self.closed_on if self.closed_on is not None else as_of
        return (end - self.raised_on).days

    def can_move_to(self, state: FindingState) -> bool:
        """Whether a transition to that state is allowed from here."""
        return state in ALLOWED_TRANSITIONS[self.state]
