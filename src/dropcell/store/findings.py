"""Reading and writing findings, and keeping the trail of what moved them.

A finding's current state is stored on the finding. Every change of state is
also written as its own row, because the question asked at an audit is never
what state a finding is in now. It is who cleared it, on what date, and what
they said at the time, and a table that only holds the current value cannot
answer that at all.

The transition is checked before it is written. A repository that will happily
move a cleared finding to scheduled is a repository that turns a state machine
into a suggestion.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from dropcell.errors import ConflictError, NotFoundError, ValidationError
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station, StationRange
from dropcell.store.base import Repository

FINDING_COLUMNS = (
    "code, line_code, kind, raised_on, start_m, end_m, summary, state, "
    "due_by, closed_on, closed_by, closed_reason, source"
)

_PLACEHOLDERS = ", ".join("?" * 13)


def row_to_finding(row: sqlite3.Row) -> Finding:
    """Rebuild a finding from a register row."""
    return Finding(
        code=str(row["code"]),
        line_code=str(row["line_code"]),
        kind=FindingKind(row["kind"]),
        raised_on=dt.date.fromisoformat(str(row["raised_on"])),
        extent=StationRange(Station(float(row["start_m"])), Station(float(row["end_m"]))),
        summary=str(row["summary"]),
        state=FindingState(row["state"]),
        due_by=None if row["due_by"] is None else dt.date.fromisoformat(str(row["due_by"])),
        closed_on=(
            None if row["closed_on"] is None else dt.date.fromisoformat(str(row["closed_on"]))
        ),
        closed_by=str(row["closed_by"]),
        closed_reason=str(row["closed_reason"]),
        source=str(row["source"]),
    )


def _values(finding: Finding) -> tuple[object, ...]:
    return (
        finding.code,
        finding.line_code,
        str(finding.kind),
        finding.raised_on.isoformat(),
        finding.extent.start.metres,
        finding.extent.end.metres,
        finding.summary,
        str(finding.state),
        None if finding.due_by is None else finding.due_by.isoformat(),
        None if finding.closed_on is None else finding.closed_on.isoformat(),
        finding.closed_by,
        finding.closed_reason,
        finding.source,
    )


class FindingRepository(Repository[Finding]):
    """Every exception raised against any line."""

    table = "finding"
    columns = FINDING_COLUMNS
    noun = "finding"
    order_by = "line_code, start_m, code"

    def to_record(self, row: sqlite3.Row) -> Finding:
        """Rebuild a finding from a register row."""
        return row_to_finding(row)

    def raise_finding(self, finding: Finding, *, actor: str = "") -> Finding:
        """Write a new finding and open its trail."""
        self.database.execute(
            f"INSERT INTO finding ({FINDING_COLUMNS}) VALUES ({_PLACEHOLDERS})",
            _values(finding),
        )
        self._record_event(
            finding.code, finding.raised_on, "none", finding.state, actor, "raised"
        )
        return finding

    def replace(self, finding: Finding) -> Finding:
        """Overwrite a stored finding without touching its trail."""
        cursor = self.database.execute(
            "UPDATE finding SET line_code = ?, kind = ?, raised_on = ?, start_m = ?,"
            " end_m = ?, summary = ?, state = ?, due_by = ?, closed_on = ?, closed_by = ?,"
            " closed_reason = ?, source = ? WHERE code = ?",
            (*_values(finding)[1:], finding.code),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("no finding with that code", code=finding.code)
        return finding

    def move(
        self,
        code: str,
        state: FindingState,
        *,
        on: dt.date,
        actor: str = "",
        reason: str = "",
    ) -> Finding:
        """Move a finding to another state, refusing a transition that is not allowed."""
        current = self.get(code)
        if not current.can_move_to(state):
            raise ConflictError(
                "a finding cannot go from one of those states to the other",
                code=current.code,
                state=str(current.state),
                wanted=str(state),
            )
        closed_on = on if state.is_closed else None
        if state is FindingState.ACCEPTED and not reason.strip():
            raise ValidationError("accepting a finding needs a reason", code=current.code)
        moved = Finding(
            code=current.code,
            line_code=current.line_code,
            kind=current.kind,
            raised_on=current.raised_on,
            extent=current.extent,
            summary=current.summary,
            state=state,
            due_by=current.due_by,
            closed_on=closed_on,
            closed_by=actor if state.is_closed else "",
            closed_reason=reason if state.is_closed else "",
            source=current.source,
        )
        self.replace(moved)
        self._record_event(current.code, on, str(current.state), state, actor, reason)
        return moved

    def _record_event(
        self,
        code: str,
        on: dt.date,
        from_state: str,
        to_state: FindingState | str,
        actor: str,
        note: str,
    ) -> None:
        self.database.execute(
            "INSERT INTO finding_event (finding_code, happened_on, from_state, to_state,"
            " actor, note) VALUES (?, ?, ?, ?, ?, ?)",
            (code, on.isoformat(), from_state, str(to_state), actor, note),
        )

    def trail(self, code: str) -> list[sqlite3.Row]:
        """Every state change on one finding, oldest first."""
        return self.database.query(
            "SELECT happened_on, from_state, to_state, actor, note FROM finding_event"
            " WHERE finding_code = ? ORDER BY id",
            (self.normalise(code),),
        )

    def open_findings(self, line_code: str | None = None) -> list[Finding]:
        """Everything still on the live register, worst placed first."""
        sql = f"SELECT {FINDING_COLUMNS} FROM finding WHERE state IN ('open', 'scheduled')"
        params: list[object] = []
        if line_code is not None:
            sql += " AND line_code = ?"
            params.append(normalise_code(line_code, kind="line code"))
        sql += " ORDER BY due_by IS NULL, due_by, code"
        return [row_to_finding(row) for row in self.database.query(sql, params)]

    def overdue(self, as_of: dt.date, line_code: str | None = None) -> list[Finding]:
        """Open findings whose date has gone."""
        return [item for item in self.open_findings(line_code) if item.is_overdue(as_of)]

    def for_line(self, line_code: str) -> list[Finding]:
        """Every finding on one line, in stationing order."""
        rows = self.database.query(
            f"SELECT {FINDING_COLUMNS} FROM finding WHERE line_code = ? ORDER BY start_m, code",
            (normalise_code(line_code, kind="line code"),),
        )
        return [row_to_finding(row) for row in rows]
