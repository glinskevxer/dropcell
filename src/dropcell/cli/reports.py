"""Commands that print a report.

Everything under here is read only. That is worth saying out loud because these
are the commands somebody runs on a Monday morning against a register they did
not build, and none of them should be able to change anything.
"""

from __future__ import annotations

import click

from dropcell.analysis.coverage import coverage
from dropcell.analysis.history import compare_years, latest_pair, years_present
from dropcell.analysis.line import assess_line
from dropcell.analysis.schedule import line_histories
from dropcell.analysis.trend import crossing_within, fit_trend, worst_drift_first
from dropcell.cli.context import Context, handled, pass_context
from dropcell.model.enums import LeadKind
from dropcell.report.annual import AnnualReport
from dropcell.report.compliance import render_compliance
from dropcell.report.exceptions import render_exceptions
from dropcell.report.export import findings_csv, readings_csv
from dropcell.report.interference import (
    PlantRow,
    bond_row,
    casing_row,
    crossing_row,
    joint_row,
    render_interference,
)
from dropcell.report.kpi import build_kpis
from dropcell.report.protection import render_protection
from dropcell.report.table import Column, Table
from dropcell.schedule.policy import STANDARD_POLICY
from dropcell.schedule.register import build_register
from dropcell.store.findings import FindingRepository
from dropcell.store.imports import ImportLedger
from dropcell.store.interference import (
    BondRepository,
    CasingRepository,
    CrossingRepository,
    IsolationJointRepository,
)
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository
from dropcell.store.tests_taken import TestHistory
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
    assessment = assess_line(
        context.database(), line_code, as_of=context.today, settings=context.settings
    )
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
@click.option(
    "--reach", default=None, help="How far a post speaks for. Defaults to the settings."
)
@pass_context
@handled
def coverage_report(context: Context, line_code: str, reach: str | None) -> None:
    """How much of the line the posts can see."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    posts = TestPointRepository(database).for_line(line.code)
    reach_m = context.settings.post_reach_m if reach is None else parse_length_m(reach)
    result = coverage(line, segments, posts, reach_m=reach_m)
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


@report_group.command("export")
@click.argument("what", type=click.Choice(["findings", "readings"]))
@click.option("--line", "line_code", required=True)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Write here instead of to standard output.",
)
@click.option("--all", "include_closed", is_flag=True, help="Closed findings as well.")
@click.option(
    "--lead",
    type=click.Choice([str(item) for item in LeadKind]),
    default=None,
    help="Only readings off this lead.",
)
@pass_context
@handled
def export(
    context: Context,
    what: str,
    line_code: str,
    out_path: str | None,
    include_closed: bool,
    lead: str | None,
) -> None:
    """Write findings or readings out as CSV."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    if what == "findings":
        findings = FindingRepository(database)
        rows = (
            findings.for_line(line.code)
            if include_closed
            else findings.open_findings(line.code)
        )
        text = findings_csv(rows, convention=line.convention)
    else:
        text = readings_csv(
            ReadingRepository(database).for_line(
                line.code, lead=None if lead is None else LeadKind(lead)
            )
        )
    if out_path is None:
        click.echo(text, nl=False)
        return
    with open(out_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    context.say(f"written to {out_path}")


TREND_COLUMNS = (
    Column("code", "Post"),
    Column("station", "Station", align="right"),
    Column("readings", "Readings", align="right"),
    Column("span", "Span yr", align="right", format=".1f"),
    Column("latest", "Latest mV", align="right", format=".0f"),
    Column("slope", "Drift mV/yr", align="right", format=".1f"),
    Column("residual", "Scatter mV", align="right", format=".0f"),
    Column("crosses", "Reaches -850"),
)


@report_group.command("kpi")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def kpi_report(context: Context, line_code: str) -> None:
    """One line's programme on one page."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    assessment = assess_line(
        database, line.code, as_of=context.today, settings=context.settings
    )
    segments = SegmentRepository(database).for_line(line.code)
    posts = TestPointRepository(database).for_line(line.code)
    register = build_register(
        STANDARD_POLICY, line_histories(database, line.code), as_of=context.today
    )
    findings = FindingRepository(database).for_line(line.code)
    kpis = build_kpis(assessment, register, coverage(line, segments, posts), findings)
    click.echo(kpis.render())


@report_group.command("trend")
@click.option("--line", "line_code", required=True)
@click.option(
    "--horizon", type=float, default=20.0, show_default=True, help="Years to look ahead."
)
@click.option(
    "--only-drifting", is_flag=True, help="Leave out posts that are not losing ground."
)
@pass_context
@handled
def trend_report(context: Context, line_code: str, horizon: float, only_drifting: bool) -> None:
    """How each post has moved over the readings it has."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    posts = TestPointRepository(database).for_line(line.code)
    readings = ReadingRepository(database)
    trends = []
    stations = {}
    for post in posts:
        history = readings.for_point(post.code, lead=LeadKind.PIPE)
        trend = fit_trend(post.code, history)
        if trend is None:
            continue
        if only_drifting and not trend.drifting_positive:
            continue
        stations[post.code] = line.format_station(post.station)
        trends.append(trend)
    table = Table(
        columns=TREND_COLUMNS,
        title=f"Drift, {line.code}",
        empty_note="no post has enough readings to fit a line through",
    )
    for trend in worst_drift_first(trends):
        crossing = trend.crosses(horizon_years=horizon)
        table.add(
            code=trend.test_point_code,
            station=stations[trend.test_point_code],
            readings=trend.readings,
            span=trend.span_years,
            latest=trend.latest_mv,
            slope=trend.slope_mv_per_year,
            residual=trend.residual_mv,
            crosses=crossing.isoformat() if crossing else "",
        )
    click.echo(table.render())
    soon = crossing_within(trends, horizon)
    click.echo("")
    click.echo(
        f"{len(soon)} of {len(trends)} fitted posts reach criterion inside {horizon:.0f} years"
    )


@report_group.command("annual")
@click.option("--line", "line_code", required=True)
@click.option("--year", type=int, default=None, help="Defaults to the year before this one.")
@click.option("--by", "prepared_by", default="", help="Who prepared it.")
@pass_context
@handled
def annual_report(context: Context, line_code: str, year: int | None, prepared_by: str) -> None:
    """The year's record, for the file rather than for this morning."""
    import datetime as dt

    database = context.database()
    line = LineRepository(database).get(line_code)
    reported = year if year is not None else context.today.year - 1
    year_end = dt.date(reported, 12, 31)
    as_of = min(year_end, context.today)
    assessment = assess_line(database, line.code, as_of=as_of, settings=context.settings)
    register = build_register(STANDARD_POLICY, line_histories(database, line.code), as_of=as_of)
    report = AnnualReport(
        year=reported,
        assessment=assessment,
        register=tuple(register),
        findings=tuple(FindingRepository(database).for_line(line.code)),
        imports=tuple(ImportLedger(database).recent(limit=500)),
        settings=context.settings,
        prepared_on=context.today,
        prepared_by=prepared_by or context.settings.operator,
    )
    click.echo(report.render())


@report_group.command("interference")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def interference_report(context: Context, line_code: str) -> None:
    """Casings, crossings, bonds and joints, with what their last test said."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    history = TestHistory(database)
    rows: list[PlantRow] = []
    for casing in CasingRepository(database).for_line(line.code):
        rows.append(casing_row(casing, history.latest_casing_test(casing)))
    for crossing in CrossingRepository(database).for_line(line.code):
        rows.append(
            crossing_row(
                crossing.code,
                crossing.station,
                crossing.foreign_operator,
                history.latest_swing_test(crossing.code),
            )
        )
    for bond in BondRepository(database).for_line(line.code):
        rows.append(bond_row(bond, history.latest_bond_check(bond.code)))
    for joint in IsolationJointRepository(database).for_line(line.code):
        rows.append(joint_row(joint, history.latest_isolation_test(joint.code)))
    click.echo(render_interference(line, rows, as_of=context.today))


CHANGE_COLUMNS = (
    Column("code", "Post"),
    Column("station", "Station", align="right"),
    Column("was", "Was mV", align="right", format=".0f"),
    Column("now", "Now mV", align="right", format=".0f"),
    Column("moved", "Moved mV", align="right", format="+.0f"),
)


@report_group.command("history")
@click.option("--line", "line_code", required=True)
@click.option("--from", "earlier", type=int, default=None, help="Earlier year.")
@click.option("--to", "later", type=int, default=None, help="Later year.")
@pass_context
@handled
def history_report(
    context: Context, line_code: str, earlier: int | None, later: int | None
) -> None:
    """Compare two years of one line, post by post."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    readings = ReadingRepository(database).for_line(line.code, lead=LeadKind.PIPE)
    years = years_present(readings)
    if earlier is None or later is None:
        pair = latest_pair(readings)
        if pair is None:
            click.echo("there are readings in fewer than two years, so nothing can be compared")
            click.echo(
                f"years with readings: {', '.join(str(year) for year in years) or 'none'}"
            )
            return
        earlier, later = pair
    result = compare_years(
        line.code,
        readings,
        earlier_year=earlier,
        later_year=later,
        threshold_mv=context.settings.protection_mv,
    )
    stations = {
        post.code: line.format_station(post.station)
        for post in TestPointRepository(database).for_line(line.code)
    }
    click.echo(result.summary())
    click.echo("")
    for title, changes in (
        ("Lost criterion", result.lost),
        ("Gained criterion", result.gained),
    ):
        table = Table(columns=CHANGE_COLUMNS, title=title, empty_note="none")
        for change in changes:
            table.add(
                code=change.test_point_code,
                station=stations.get(change.test_point_code, ""),
                was=change.was_mv,
                now=change.now_mv,
                moved=change.movement_mv,
            )
        click.echo(table.render())
        click.echo("")
    click.echo(
        f"{len(result.held)} posts held their side, "
        f"{len(result.only_earlier)} were read only in {earlier}, "
        f"{len(result.only_later)} only in {later}"
    )
