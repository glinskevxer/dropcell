from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.coverage import coverage
from dropcell.analysis.line import assess_line
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.report.kpi import build_kpis
from dropcell.schedule.policy import STANDARD_POLICY, AssetKind
from dropcell.schedule.register import AssetHistory, build_register
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository

TODAY = dt.date(2025, 3, 14)


@pytest.fixture
def register(database: Database, line: Line, segment: Segment) -> Database:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    posts = TestPointRepository(database)
    for code, metres in (("TP-1", 100.0), ("TP-2", 600.0), ("TP-3", 900.0)):
        posts.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(metres),
                leads=frozenset({LeadKind.PIPE}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
    readings = ReadingRepository(database)
    readings.add(
        Reading(
            test_point_code="TP-1",
            lead=LeadKind.PIPE,
            taken_on=TODAY,
            on_mv=-1120.0,
            off_mv=-905.0,
        )
    )
    readings.add(
        Reading(
            test_point_code="TP-2",
            lead=LeadKind.PIPE,
            taken_on=TODAY,
            on_mv=-1020.0,
            off_mv=-780.0,
        )
    )
    return database


def finding(**overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "code": "F-2025-001",
        "line_code": "AL-2",
        "kind": FindingKind.UNDER_CRITERION,
        "raised_on": dt.date(2025, 1, 10),
        "extent": StationRange(Station(600.0), Station(660.0)),
        "summary": "sixty metres under criterion",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)  # type: ignore[arg-type]


def build(register: Database, line: Line, findings: list[Finding]):  # type: ignore[no-untyped-def]
    assessment = assess_line(register, "AL-2", as_of=TODAY)
    posts = TestPointRepository(register).for_line("AL-2")
    segments = SegmentRepository(register).for_line("AL-2")
    histories = [
        AssetHistory(code=post.code, kind=AssetKind.TEST_POINT, visits=(TODAY,))
        for post in posts
    ]
    due = build_register(STANDARD_POLICY, histories, as_of=TODAY)
    return build_kpis(assessment, due, coverage(line, segments, posts), findings)


def test_the_counts_come_straight_off_the_assessment(register: Database, line: Line) -> None:
    kpis = build(register, line, [])
    assert kpis.posts == 3
    assert kpis.judged_posts == 2
    assert kpis.protected_posts == 1
    assert kpis.never_read_posts == 1


def test_the_protection_rate_is_over_judged_posts(register: Database, line: Line) -> None:
    kpis = build(register, line, [])
    assert kpis.protection_rate == pytest.approx(0.5)


def test_the_coverage_share_is_over_line_length(register: Database, line: Line) -> None:
    kpis = build(register, line, [])
    assert 0.0 < kpis.covered_share < 1.0
    assert kpis.longest_gap_m > 0


def test_closed_findings_are_left_out_of_every_finding_figure(
    register: Database, line: Line
) -> None:
    closed = finding(
        code="F-2025-002",
        state=FindingState.CLEARED,
        closed_on=dt.date(2025, 2, 1),
    )
    kpis = build(register, line, [finding(), closed])
    assert kpis.open_findings == 1
    assert kpis.finding_length_m == pytest.approx(60.0)


def test_an_overdue_finding_is_counted_separately(register: Database, line: Line) -> None:
    kpis = build(register, line, [finding(due_by=dt.date(2025, 1, 20))])
    assert kpis.open_findings == 1
    assert kpis.overdue_findings == 1


def test_every_row_carries_what_it_is_measured_over(register: Database, line: Line) -> None:
    rows = build(register, line, []).rows()
    assert all(over for _, _, over in rows)
    by_figure = {figure: over for figure, _, over in rows}
    assert "posts that could be judged" in by_figure["protection rate"]
    assert by_figure["monitoring compliance"] == "asset and rule pairs"
    assert by_figure["line within reach of a post"] == "line length"


def test_the_never_read_count_says_it_is_not_a_rate(register: Database, line: Line) -> None:
    rows = {figure: over for figure, _, over in build(register, line, []).rows()}
    assert rows["posts never read"] == "count, not a rate"


def test_the_slide_renders_with_a_title(register: Database, line: Line) -> None:
    rendered = build(register, line, []).render()
    assert "Programme, AL-2, as at 2025-03-14" in rendered
    assert "protection rate" in rendered
    assert "50.0%" in rendered
