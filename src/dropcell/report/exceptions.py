"""The exception register, printed.

The register has one job in a meeting: to make the argument about what gets
done next take five minutes instead of an hour. That means the order on the
page has to be the order the work should happen in, and the columns have to be
the ones somebody would otherwise ask for out loud.

Overdue findings come first, worst overdue at the top, because those are the
ones that have already failed a commitment. Then everything else by its date,
soonest first. Findings with no date at all go last, since nobody promised
anything about them, and they are the ones that quietly stay open for years.

The summary line under the table is the part that gets read. It carries the
counts that decide whether this is a normal month.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.findings.finding import Finding, FindingKind
from dropcell.report.table import Column, Table
from dropcell.stationing import Convention

EXCEPTION_COLUMNS = (
    Column("code", "Finding"),
    Column("kind", "Kind", width=18),
    Column("from", "From", align="right"),
    Column("to", "To", align="right"),
    Column("length", "Length m", align="right", format=".0f"),
    Column("raised", "Raised"),
    Column("due", "Due"),
    Column("age", "Age d", align="right"),
    Column("state", "State"),
    Column("summary", "Summary", width=40),
)


def sort_key(finding: Finding, as_of: dt.date) -> tuple[int, int, str]:
    """Overdue first and worst overdue at the top, then by date, then undated.

    Closed findings go behind all of those. They are on the report because
    somebody wants to see what was dealt with, not because anybody has to do
    anything about them, and a cleared finding that was late while it was open
    would otherwise sit above live work forever.
    """
    if not finding.is_open:
        return (3, 0, finding.code)
    if finding.is_overdue(as_of):
        assert finding.due_by is not None
        return (0, -(as_of - finding.due_by).days, finding.code)
    if finding.due_by is None:
        return (2, 0, finding.code)
    return (1, (finding.due_by - as_of).days, finding.code)


def order(findings: list[Finding], as_of: dt.date) -> list[Finding]:
    """Put the register in the order the work should happen in."""
    return sorted(findings, key=lambda item: sort_key(item, as_of))


@dataclass(frozen=True)
class ExceptionSummary:
    """The counts under the table."""

    total: int
    overdue: int
    open_findings: int
    closed: int
    total_length_m: float

    def render(self) -> str:
        """One line for the bottom of the report."""
        return (
            f"{self.total} findings, {self.open_findings} open, {self.overdue} overdue, "
            f"{self.total_length_m:.0f} m of pipe"
        )


def summarise(findings: list[Finding], as_of: dt.date) -> ExceptionSummary:
    """Count what the register holds."""
    return ExceptionSummary(
        total=len(findings),
        overdue=sum(1 for item in findings if item.is_overdue(as_of)),
        open_findings=sum(1 for item in findings if item.is_open),
        closed=sum(1 for item in findings if not item.is_open),
        total_length_m=sum(item.length_m for item in findings),
    )


def exception_table(
    findings: list[Finding],
    *,
    as_of: dt.date,
    convention: Convention = Convention.FOOT,
    title: str = "Exception register",
    by_kind: bool = False,
) -> Table:
    """Build the table of findings.

    Grouped by kind the register reads as a set of problems; ungrouped it reads
    as a work list. Both are wanted and by different people, so the ordering
    inside a group stays the one the work should happen in either way.
    """
    table = Table(columns=EXCEPTION_COLUMNS, title=title, empty_note="no exceptions raised")
    ordered = (
        sorted(order(findings, as_of), key=lambda item: str(item.kind))
        if by_kind
        else order(findings, as_of)
    )
    if by_kind:
        table.group_by("kind")
    for finding in ordered:
        table.add(
            code=finding.code,
            kind=str(finding.kind),
            **{
                "from": finding.extent.start.format(convention),
                "to": finding.extent.end.format(convention),
            },
            length=finding.length_m,
            raised=finding.raised_on.isoformat(),
            due="" if finding.due_by is None else finding.due_by.isoformat(),
            age=finding.age_days(as_of),
            state=str(finding.state),
            summary=finding.summary,
        )
    return table


def render_exceptions(
    findings: list[Finding],
    *,
    as_of: dt.date,
    convention: Convention = Convention.FOOT,
    title: str = "Exception register",
    by_kind: bool = False,
) -> str:
    """The whole report, table and summary."""
    table = exception_table(
        findings, as_of=as_of, convention=convention, title=title, by_kind=by_kind
    )
    summary = summarise(findings, as_of)
    return f"{table.render()}\n\n{summary.render()}"


def by_kind(findings: list[Finding]) -> dict[FindingKind, list[Finding]]:
    """The register split up by what sort of exception each one is."""
    grouped: dict[FindingKind, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.kind, []).append(finding)
    return grouped
