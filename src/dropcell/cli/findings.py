"""Commands for the exception register.

The state changes are separate commands rather than one command with a state
option, because they are not the same operation. Scheduling takes a date.
Clearing takes evidence. Accepting takes a name and a reason and is the only one
of the three that closes a finding without anybody fixing anything, so it is the
one that should be a little bit awkward to type.

Every one of them writes to the trail. The trail is the answer to the only
question an auditor ever asks about a closed finding, which is who closed it and
what they said at the time.
"""

from __future__ import annotations

import datetime as dt

import click

from dropcell.cli.common import line_span
from dropcell.cli.context import Context, handled, pass_context
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.findings.raise_from import format_code, next_sequence
from dropcell.report.table import Column, Table
from dropcell.stationing import StationRange
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository

TRAIL_COLUMNS = (
    Column("when", "When"),
    Column("from", "From"),
    Column("to", "To"),
    Column("who", "Who", width=18),
    Column("note", "Note", width=44),
)


@click.group("finding")
def finding_group() -> None:
    """Raise, move and close exceptions."""


@finding_group.command("raise")
@click.option("--line", "line_code", required=True)
@click.option(
    "--kind",
    type=click.Choice([str(item) for item in FindingKind]),
    required=True,
)
@click.option("--from", "start", required=True, help="Start station.")
@click.option("--to", "end", default=None, help="End station, defaults to the start.")
@click.option("--summary", required=True, help="One line saying what is wrong.")
@click.option("--due", default=None, help="Date something has to happen by.")
@click.option("--source", default="", help="Where the finding came from.")
@click.option("--by", "actor", default="", help="Who raised it.")
@pass_context
@handled
def raise_finding(
    context: Context,
    line_code: str,
    kind: str,
    start: str,
    end: str | None,
    summary: str,
    due: str | None,
    source: str,
    actor: str,
) -> None:
    """Raise an exception against a stretch of line."""
    database = context.database()
    line, first, last = line_span(database, line_code, start, end)
    findings = FindingRepository(database)
    code = format_code(
        context.today.year,
        next_sequence([item.code for item in findings.all()], context.today.year),
    )
    finding = Finding(
        code=code,
        line_code=line.code,
        kind=FindingKind(kind),
        raised_on=context.today,
        extent=StationRange(first, last),
        summary=summary,
        due_by=dt.date.fromisoformat(due) if due else None,
        source=source,
    )
    findings.raise_finding(finding, actor=actor)
    click.echo(f"{finding.code} raised on {line.code}")


@finding_group.command("schedule")
@click.argument("code")
@click.option("--by", "actor", default="")
@click.option("--note", default="work raised")
@pass_context
@handled
def schedule_finding(context: Context, code: str, actor: str, note: str) -> None:
    """Mark a finding as having work booked against it."""
    findings = FindingRepository(context.database())
    moved = findings.move(
        code, FindingState.SCHEDULED, on=context.today, actor=actor, reason=note
    )
    click.echo(f"{moved.code} scheduled")


@finding_group.command("clear")
@click.argument("code")
@click.option("--by", "actor", required=True, help="Who is clearing it.")
@click.option("--note", default="", help="What proved it was fixed.")
@pass_context
@handled
def clear_finding(context: Context, code: str, actor: str, note: str) -> None:
    """Close a finding that has been fixed and re-read."""
    findings = FindingRepository(context.database())
    moved = findings.move(
        code, FindingState.CLEARED, on=context.today, actor=actor, reason=note
    )
    click.echo(f"{moved.code} cleared on {moved.closed_on}")


@finding_group.command("accept")
@click.argument("code")
@click.option("--by", "actor", required=True, help="Who is accepting it.")
@click.option("--reason", required=True, help="Why it is being lived with.")
@pass_context
@handled
def accept_finding(context: Context, code: str, actor: str, reason: str) -> None:
    """Close a finding without fixing it, on somebody's authority."""
    findings = FindingRepository(context.database())
    moved = findings.move(
        code, FindingState.ACCEPTED, on=context.today, actor=actor, reason=reason
    )
    click.echo(f"{moved.code} accepted by {actor}")


@finding_group.command("reopen")
@click.argument("code")
@click.option("--by", "actor", default="")
@click.option("--note", default="came back")
@pass_context
@handled
def reopen_finding(context: Context, code: str, actor: str, note: str) -> None:
    """Put a closed finding back on the live register."""
    findings = FindingRepository(context.database())
    moved = findings.move(code, FindingState.OPEN, on=context.today, actor=actor, reason=note)
    click.echo(f"{moved.code} reopened")


@finding_group.command("show")
@click.argument("code")
@pass_context
@handled
def show_finding(context: Context, code: str) -> None:
    """Show one finding and everything that has happened to it."""
    database = context.database()
    findings = FindingRepository(database)
    finding = findings.get(code)
    line = LineRepository(database).get(finding.line_code)
    click.echo(f"{finding.code}  {finding.kind}  on {line.code}")
    click.echo(f"where    {finding.extent.format(line.convention)}")
    click.echo(f"raised   {finding.raised_on.isoformat()}")
    click.echo(f"due      {finding.due_by.isoformat() if finding.due_by else 'no date'}")
    click.echo(f"state    {finding.state}")
    click.echo(f"summary  {finding.summary}")
    if finding.source:
        click.echo(f"source   {finding.source}")
    click.echo("")
    table = Table(columns=TRAIL_COLUMNS, title="Trail")
    for row in findings.trail(finding.code):
        table.add(
            when=row["happened_on"],
            **{"from": row["from_state"], "to": row["to_state"]},
            who=row["actor"],
            note=row["note"],
        )
    click.echo(table.render())
