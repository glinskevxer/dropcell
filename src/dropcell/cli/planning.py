"""Reports that look forward or back rather than at this morning.

The split from the other report group is not about what the code does, it is
about who reads it. Protection, exceptions and compliance answer questions
somebody has today. The programme page, the drift, the year on year comparison
and the segment ranking are read once a quarter by somebody deciding where next
year's money goes, and they were getting lost in a list of thirty commands.
"""

from __future__ import annotations

import click

from dropcell.analysis.balance import balance
from dropcell.analysis.coating import assess_coating, share_out, worst_first
from dropcell.analysis.coverage import coverage
from dropcell.analysis.history import compare_years, latest_pair, years_present
from dropcell.analysis.line import assess_line
from dropcell.analysis.risk import by_exposure, score_segment, total_exposure
from dropcell.analysis.risk import rank as rank_risk
from dropcell.analysis.schedule import line_histories
from dropcell.analysis.survey_plan import budget_for, plan_surveys
from dropcell.analysis.trend import crossing_within, fit_trend, worst_drift_first
from dropcell.cli.context import Context, handled, pass_context
from dropcell.errors import NotFoundError
from dropcell.model.enums import LeadKind
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.report.estate import LineSummary, render_estate
from dropcell.report.kpi import build_kpis
from dropcell.report.table import Column, Table
from dropcell.schedule.policy import STANDARD_POLICY
from dropcell.schedule.register import build_register
from dropcell.stationing import Station
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.rectifiers import RectifierCheckRepository, RectifierRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository


@click.group("plan")
def plan_group() -> None:
    """Reports for deciding where next year's work goes."""


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


@plan_group.command("kpi")
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


@plan_group.command("trend")
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


CHANGE_COLUMNS = (
    Column("code", "Post"),
    Column("station", "Station", align="right"),
    Column("was", "Was mV", align="right", format=".0f"),
    Column("now", "Now mV", align="right", format=".0f"),
    Column("moved", "Moved mV", align="right", format="+.0f"),
)


@plan_group.command("history")
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


RISK_COLUMNS = (
    Column("code", "Segment"),
    Column("from", "From", align="right"),
    Column("to", "To", align="right"),
    Column("length", "Length m", align="right", format=".0f"),
    Column("coating", "Coating", width=16),
    Column("surveyed", "Last walked"),
    Column("covered", "In reach", align="right", format=".0%"),
    Column("score", "Score", align="right", format=".2f"),
    Column("exposure", "Score km", align="right", format=".2f"),
)


@plan_group.command("risk")
@click.option("--line", "line_code", required=True)
@click.option("--by-length", is_flag=True, help="Order by score weighted by length.")
@click.option("--explain", is_flag=True, help="Write the scoring out underneath.")
@pass_context
@handled
def risk_report(context: Context, line_code: str, by_length: bool, explain: bool) -> None:
    """Where the next survey and the next rectifier should go."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    posts = TestPointRepository(database).for_line(line.code)
    reach = context.settings.post_reach_m
    scores = []
    walked: dict[str, str] = {}
    for segment in segments:
        covered = _covered_share(segment, posts, reach)
        scores.append(
            score_segment(
                segment,
                as_of=context.today,
                years_since_survey=None,
                covered_share=covered,
            )
        )
        walked[segment.code] = "never"
    ordered = by_exposure(scores) if by_length else rank_risk(scores)
    table = Table(
        columns=RISK_COLUMNS,
        title=f"Segment risk, {line.code}",
        empty_note="no segments on this line",
    )
    by_code = {segment.code: segment for segment in segments}
    for score in ordered:
        segment = by_code[score.segment_code]
        table.add(
            code=score.segment_code,
            **{
                "from": segment.extent.start.format(line.convention),
                "to": segment.extent.end.format(line.convention),
            },
            length=score.length_m,
            coating=str(segment.coating),
            surveyed=walked[score.segment_code],
            covered=_covered_share(segment, posts, reach),
            score=score.score,
            exposure=score.exposure,
        )
    click.echo(table.render())
    click.echo("")
    click.echo(f"{len(scores)} segments, total exposure {total_exposure(scores):.1f} score km")
    if explain:
        click.echo("")
        for score in ordered:
            click.echo(f"  {score.explain()}")


def _covered_share(segment: Segment, posts: list[TestPoint], reach_m: float) -> float:
    """How much of a segment sits inside the reach of some post."""
    if segment.length_m <= 0:
        return 0.0
    covered = 0.0
    cursor = segment.extent.start.metres
    for post in sorted(posts, key=lambda item: item.station.metres):
        low = max(segment.extent.start.metres, post.station.metres - reach_m)
        high = min(segment.extent.end.metres, post.station.metres + reach_m)
        if high <= low:
            continue
        low = max(low, cursor)
        if high > low:
            covered += high - low
            cursor = high
    return min(1.0, covered / segment.length_m)


@plan_group.command("estate")
@pass_context
@handled
def estate_report(context: Context) -> None:
    """Every line in the register on one page."""
    database = context.database()
    lines = LineRepository(database).all()
    findings = FindingRepository(database)
    summaries: list[LineSummary] = []
    for line in lines:
        posts = TestPointRepository(database).for_line(line.code)
        judged = 0
        protected = 0
        unread = 0
        if posts:
            try:
                assessment = assess_line(
                    database, line.code, as_of=context.today, settings=context.settings
                )
            except NotFoundError:
                assessment = None
            if assessment is not None:
                judged = len(assessment.assessed)
                protected = len(assessment.protected)
                unread = len(assessment.unread)
        register = build_register(
            STANDARD_POLICY, line_histories(database, line.code), as_of=context.today
        )
        late = [item for item in register if item.overdue or not item.ever_visited]
        open_findings = [item for item in findings.for_line(line.code) if item.is_open]
        summaries.append(
            LineSummary(
                code=line.code,
                name=line.name,
                length_m=line.length_m,
                posts=len(posts),
                judged=judged,
                protected=protected,
                unread=unread,
                overdue=len(late),
                open_findings=len(open_findings),
            )
        )
    click.echo(render_estate(summaries, as_of=context.today))


COATING_COLUMNS = (
    Column("code", "Segment"),
    Column("coating", "Coating", width=16),
    Column("area", "Area m2", align="right", format=".0f"),
    Column("design", "As laid mA", align="right", format=".1f"),
    Column("drawn", "Drawing mA", align="right", format=".0f"),
    Column("factor", "Factor", align="right", format=".0f"),
    Column("bare", "Implied bare m2", align="right", format=".2f"),
    Column("verdict", "Coating", width=20),
)


@plan_group.command("coating")
@click.option("--line", "line_code", required=True)
@click.option(
    "--current",
    "measured",
    default=None,
    help="Total current on the line, such as 12.4 A. Defaults to the rectifier checks.",
)
@click.option("--explain", is_flag=True, help="Write each comparison out underneath.")
@pass_context
@handled
def coating_report(
    context: Context, line_code: str, measured: str | None, explain: bool
) -> None:
    """What the current draw says about the coating.

    The output is split across the segments by their design current, which is a
    guess and is stated as one on the page. A line with one segment gets an
    exact answer; a line with six gets six answers that add up to the right
    total and are individually approximate.
    """
    from dropcell.units import parse_current_a

    database = context.database()
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    if not segments:
        click.echo("no segments on this line, so there is nothing to compare against")
        return
    if measured is not None:
        total_ma = parse_current_a(measured) * 1000.0
        source = "the current given on the command line"
    else:
        checks = RectifierCheckRepository(database)
        latest = [
            checks.latest(unit.tag)
            for unit in RectifierRepository(database).for_line(line.code)
        ]
        readings = [item for item in latest if item is not None]
        if not readings:
            click.echo("no rectifier has been read on this line and no current was given")
            return
        total_ma = sum(item.output_current_a for item in readings) * 1000.0
        source = f"the last check on {len(readings)} rectifiers"
    split = share_out(segments, total_ma)
    conditions = [assess_coating(segment, split[segment.code]) for segment in segments]
    table = Table(
        columns=COATING_COLUMNS,
        title=f"Coating condition, {line.code}",
        empty_note="nothing to compare",
    )
    for condition in worst_first(conditions):
        table.add(
            code=condition.segment_code,
            coating=str(condition.coating),
            area=condition.area_m2,
            design=condition.design_current_ma,
            drawn=condition.measured_current_ma,
            factor=condition.breakdown_factor,
            bare=condition.implied_bare_area_m2,
            verdict=condition.verdict,
        )
    click.echo(table.render())
    click.echo("")
    click.echo(f"{total_ma / 1000.0:.2f} A on the line, from {source}")
    if len(segments) > 1:
        click.echo("split across the segments by design current, which is a guess")
    worth = [item for item in conditions if item.is_worth_investigating]
    click.echo(f"{len(worth)} of {len(conditions)} segments are worth a gradient survey")
    if explain:
        click.echo("")
        for condition in worst_first(conditions):
            click.echo(f"  {condition.explain()}")


BALANCE_COLUMNS = (
    Column("tag", "Unit"),
    Column("station", "Station", align="right"),
    Column("rated", "Rated A", align="right", format=".0f"),
    Column("output", "Output A", align="right", format=".2f"),
    Column("load", "Of rating", align="right", format=".0%"),
    Column("share", "Of line", align="right", format=".0%"),
    Column("spare", "Spare A", align="right", format=".1f"),
    Column("state", "State", width=14),
)


@plan_group.command("balance")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def balance_report(context: Context, line_code: str) -> None:
    """How the units on a line are sharing the work.

    A line with four rectifiers and a comfortable protection rate can be a line
    with one rectifier and three ornaments, and no other page here can tell
    those apart.
    """
    database = context.database()
    line = LineRepository(database).get(line_code)
    units = RectifierRepository(database).for_line(line.code)
    if not units:
        click.echo("no rectifiers on this line")
        return
    checks = RectifierCheckRepository(database)
    latest = {unit.tag: checks.latest(unit.tag) for unit in units}
    result = balance(units, latest)
    table = Table(columns=BALANCE_COLUMNS, title=f"Load sharing, {line.code}")
    for share in sorted(result.units, key=lambda item: -item.output_a):
        state = "dead" if share.is_dead else ("at capacity" if not share.has_headroom else "")
        table.add(
            tag=share.tag,
            station=line.format_station(Station(share.station_m)),
            rated=share.rated_a,
            output=share.output_a,
            load=share.load,
            share=share.share,
            spare=share.spare_a,
            state=state,
        )
    click.echo(table.render())
    click.echo("")
    click.echo(result.summary())
    if result.is_concentrated:
        click.echo("  one unit is carrying most of this line")
    gap = result.widest_gap_m()
    if gap is not None:
        click.echo(f"  the widest gap between neighbouring units is {gap:.0f} m")
    if result.can_lose_the_biggest:
        click.echo(f"  {result.spare_a:.1f} A spare, enough rating to lose the largest unit")
    else:
        click.echo("  not enough spare rating anywhere to take up the largest unit's output")


PLAN_COLUMNS = (
    Column("code", "Segment"),
    Column("line", "Line"),
    Column("length", "Walk km", align="right", format=".2f"),
    Column("score", "Score", align="right", format=".2f"),
    Column("state", "In the plan"),
)


@plan_group.command("survey")
@click.option("--budget", type=float, required=True, help="Kilometres to be walked.")
@click.option("--line", "line_code", default=None, help="Only this line.")
@pass_context
@handled
def survey_plan(context: Context, budget: float, line_code: str | None) -> None:
    """Fill a survey budget with the worst pipe that fits in it."""
    database = context.database()
    lines = (
        [LineRepository(database).get(line_code)]
        if line_code
        else LineRepository(database).in_service()
    )
    scores = []
    owners: dict[str, str] = {}
    for line in lines:
        posts = TestPointRepository(database).for_line(line.code)
        for segment in SegmentRepository(database).for_line(line.code):
            owners[segment.code] = line.code
            scores.append(
                score_segment(
                    segment,
                    as_of=context.today,
                    covered_share=_covered_share(segment, posts, context.settings.post_reach_m),
                )
            )
    if not scores:
        click.echo("no segments anywhere to plan a survey over")
        return
    plan = plan_surveys(scores, owners, budget_km=budget)
    table = Table(columns=PLAN_COLUMNS, title=f"Survey plan, {budget:.1f} km")
    for item in plan.walking:
        table.add(
            code=item.segment_code,
            line=item.line_code,
            length=item.length_km,
            score=item.score,
            state="walk",
        )
    for item in plan.skipped:
        table.add(
            code=item.segment_code,
            line=item.line_code,
            length=item.length_km,
            score=item.score,
            state="not reached",
        )
    click.echo(table.render())
    click.echo("")
    click.echo(plan.summary())
    if plan.spare_km > 0:
        click.echo(f"  {plan.spare_km:.1f} km of budget unspent")
    worst = plan.worst_skipped
    if worst is not None:
        needed = budget_for(scores, above_score=worst.score)
        click.echo(
            f"  the worst segment not reached is {worst.segment_code} at "
            f"{worst.score:.2f}; walking everything at least that bad needs "
            f"{needed:.1f} km"
        )
