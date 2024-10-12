"""Commands that print a report.

Everything under here is read only. That is worth saying out loud because these
are the commands somebody runs on a Monday morning against a register they did
not build, and none of them should be able to change anything.
"""

from __future__ import annotations

import click

from dropcell.analysis.coverage import coverage
from dropcell.analysis.line import assess_line
from dropcell.analysis.schedule import line_histories
from dropcell.cli.context import Context, handled, pass_context
from dropcell.report.compliance import render_compliance
from dropcell.report.exceptions import render_exceptions
from dropcell.report.protection import render_protection
from dropcell.report.table import Column, Table
from dropcell.schedule.policy import STANDARD_POLICY
from dropcell.schedule.register import build_register
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository
from dropcell.units import parse_length_m

GAP_COLUMNS = (
    Column("from", "From", align="right"),
    Column("to", "To", align="right"),
    Column("length", "Length m", align="right", format=".0f"),
    Column("before", "After post"),
    Column("after", "Before post"),
)


@click.group("report")
def report_group() -> None:
    """Print a report. Nothing under here writes anything."""


@report_group.command("protection")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def protection_report(context: Context, line_code: str) -> None:
    """How the posts on one line read."""
    assessment = assess_line(context.database(), line_code, as_of=context.today)
    click.echo(render_protection(assessment))


@report_group.command("exceptions")
@click.option("--line", "line_code", default=None, help="Only this line.")
@click.option("--all", "include_closed", is_flag=True, help="Closed findings as well.")
@pass_context
@handled
def exceptions_report(context: Context, line_code: str | None, include_closed: bool) -> None:
    """What is on the exception register."""
    database = context.database()
    findings = FindingRepository(database)
    if include_closed:
        found = findings.for_line(line_code) if line_code else findings.all()
    else:
        found = findings.open_findings(line_code)
    convention = LineRepository(database).get(line_code).convention if line_code else None
    title = f"Exception register, {line_code}" if line_code else "Exception register"
    if convention is None:
        click.echo(render_exceptions(found, as_of=context.today, title=title))
        return
    click.echo(
        render_exceptions(found, as_of=context.today, convention=convention, title=title)
    )


@report_group.command("compliance")
@click.option("--line", "line_code", required=True)
@click.option("--window", type=int, default=90, show_default=True, help="Days to look ahead.")
@pass_context
@handled
def compliance_report(context: Context, line_code: str, window: int) -> None:
    """What is overdue and what falls due."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    register = build_register(
        STANDARD_POLICY, line_histories(database, line.code), as_of=context.today
    )
    click.echo(
        render_compliance(
            register,
            as_of=context.today,
            days=window,
            title=f"Monitoring compliance, {line.code}",
        )
    )


@report_group.command("coverage")
@click.option("--line", "line_code", required=True)
@click.option("--reach", default="1600 m", show_default=True, help="How far a post speaks for.")
@pass_context
@handled
def coverage_report(context: Context, line_code: str, reach: str) -> None:
    """How much of the line the posts can see."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    posts = TestPointRepository(database).for_line(line.code)
    result = coverage(line, segments, posts, reach_m=parse_length_m(reach))
    click.echo(f"Coverage, {line.code} {line.name}")
    click.echo(f"as at {context.today.isoformat()}")
    click.echo("")
    click.echo(
        f"{result.posts} posts over {result.length_m:.0f} m, "
        f"{result.covered_share:.1%} within {result.reach_m:.0f} m of a post"
    )
    if result.mean_spacing_m is not None:
        click.echo(f"mean spacing {result.mean_spacing_m:.0f} m")
    if result.segments_without_posts:
        click.echo(f"segments with no post: {', '.join(result.segments_without_posts)}")
    click.echo("")
    table = Table(columns=GAP_COLUMNS, title="Gaps", empty_note="no gaps at this reach")
    for gap in result.gaps:
        table.add(
            **{
                "from": gap.extent.start.format(line.convention),
                "to": gap.extent.end.format(line.convention),
                "before": gap.before or "start of line",
                "after": gap.after or "end of line",
            },
            length=gap.length_m,
        )
    click.echo(table.render())
