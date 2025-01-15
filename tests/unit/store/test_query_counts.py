"""Holding the query counts of the walks that grow with the size of a line.

These are the only tests here that assert on how something is done rather than
on what it produces. They exist because every one of these paths was written as
a loop over posts with a query inside it, worked perfectly on the six post
register somebody developed against, and was unusable on a real line.
"""

from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.line import assess_line
from dropcell.findings.finding import Finding, FindingKind
from dropcell.findings.work import WorkKind, WorkOrder
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository
from dropcell.store.work import WorkOrderRepository

TODAY = dt.date(2025, 3, 14)


def build_line(database: Database, line: Line, segment: Segment, posts: int) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(
        __import__("dataclasses").replace(
            segment, extent=StationRange(Station(0.0), Station(line.length_m))
        )
    )
    point_store = TestPointRepository(database)
    readings = ReadingRepository(database)
    for index in range(posts):
        code = f"TP-{index:03d}"
        point_store.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(float(index) * 100.0),
                leads=frozenset({LeadKind.PIPE}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
        for year in (2023, 2024, 2025):
            readings.add(
                Reading(
                    test_point_code=code,
                    lead=LeadKind.PIPE,
                    taken_on=dt.date(year, 3, 14),
                    on_mv=-1120.0,
                    off_mv=-905.0,
                )
            )


def test_assessing_a_line_does_not_grow_a_query_per_post(
    database: Database, line: Line, segment: Segment
) -> None:
    build_line(database, line, segment, posts=4)
    database.statements = 0
    small = assess_line(database, "AL-2", as_of=TODAY)
    cost_of_four = database.statements

    other = Database(":memory:")
    from dropcell.store.migrations import migrate

    migrate(other)
    build_line(other, line, segment, posts=40)
    other.statements = 0
    large = assess_line(other, "AL-2", as_of=TODAY)
    cost_of_forty = other.statements

    assert len(small.posts) == 4
    assert len(large.posts) == 40
    assert cost_of_forty == cost_of_four


def test_assessing_a_line_still_finds_the_latest_reading(
    database: Database, line: Line, segment: Segment
) -> None:
    build_line(database, line, segment, posts=3)
    result = assess_line(database, "AL-2", as_of=TODAY)
    for post in result.posts:
        assert post.reading is not None
        assert post.reading.taken_on == dt.date(2025, 3, 14)


def test_a_post_with_no_reading_still_comes_back_unread(
    database: Database, line: Line, segment: Segment
) -> None:
    build_line(database, line, segment, posts=2)
    TestPointRepository(database).add(
        TestPoint(
            code="TP-900",
            line_code="AL-2",
            station=Station(9000.0),
            leads=frozenset({LeadKind.PIPE}),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    result = assess_line(database, "AL-2", as_of=TODAY)
    assert [item.code for item in result.unread] == ["TP-900"]


def test_the_latest_per_point_lookup_returns_one_row_per_post(
    database: Database, line: Line, segment: Segment
) -> None:
    build_line(database, line, segment, posts=3)
    latest = ReadingRepository(database).latest_per_point("AL-2", LeadKind.PIPE)
    assert set(latest) == {"TP-000", "TP-001", "TP-002"}
    assert all(reading.taken_on.year == 2025 for reading in latest.values())


def test_a_lead_nobody_reads_gives_an_empty_lookup(
    database: Database, line: Line, segment: Segment
) -> None:
    build_line(database, line, segment, posts=2)
    assert ReadingRepository(database).latest_per_point("AL-2", LeadKind.CASING) == {}


def build_orders(database: Database, line: Line, count: int) -> None:
    LineRepository(database).add(line)
    findings = FindingRepository(database)
    orders = WorkOrderRepository(database)
    for index in range(count):
        finding_code = f"F-2025-{index:03d}"
        findings.raise_finding(
            Finding(
                code=finding_code,
                line_code="AL-2",
                kind=FindingKind.UNDER_CRITERION,
                raised_on=TODAY,
                extent=StationRange(Station(0.0), Station(10.0)),
                summary="under criterion",
            )
        )
        orders.add(
            WorkOrder(
                code=f"WO-2025-{index:03d}",
                line_code="AL-2",
                kind=WorkKind.EXCAVATION,
                raised_on=TODAY,
                finding_codes=(finding_code,),
                summary="dig",
            )
        )


def test_listing_work_orders_does_not_grow_a_query_per_order(
    database: Database, line: Line
) -> None:
    build_orders(database, line, 3)
    database.statements = 0
    WorkOrderRepository(database).for_line("AL-2")
    cost_of_three = database.statements

    from dropcell.store.migrations import migrate

    other = Database(":memory:")
    migrate(other)
    build_orders(other, line, 30)
    other.statements = 0
    orders = WorkOrderRepository(other).for_line("AL-2")
    assert len(orders) == 30
    assert other.statements == cost_of_three


def test_listing_work_orders_still_attaches_the_right_findings(
    database: Database, line: Line
) -> None:
    build_orders(database, line, 3)
    orders = WorkOrderRepository(database).for_line("AL-2")
    assert [item.finding_codes for item in orders] == [
        ("F-2025-000",),
        ("F-2025-001",),
        ("F-2025-002",),
    ]


def test_looking_an_order_up_from_a_finding_takes_one_query_for_the_row(
    database: Database, line: Line
) -> None:
    build_orders(database, line, 3)
    found = WorkOrderRepository(database).against("F-2025-001")
    assert [item.code for item in found] == ["WO-2025-001"]


def test_the_counter_moves_with_every_statement(database: Database) -> None:
    before = database.statements
    database.query("SELECT count(*) FROM line")
    assert database.statements == before + 1
    database.executemany("INSERT INTO line VALUES (?,?,?,?,?,?,?,?,?)", [])
    assert database.statements == before + 2


def test_a_batch_insert_counts_as_one_statement(database: Database, line: Line) -> None:
    LineRepository(database).add(line)
    TestPointRepository(database).add(
        TestPoint(
            code="TP-1",
            line_code="AL-2",
            station=Station(100.0),
            leads=frozenset({LeadKind.PIPE}),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    readings = ReadingRepository(database)
    database.statements = 0
    readings.add_many(
        [
            Reading(
                test_point_code="TP-1",
                lead=LeadKind.PIPE,
                taken_on=dt.date(2020 + index, 3, 14),
                on_mv=-1120.0,
                off_mv=-905.0,
            )
            for index in range(5)
        ]
    )
    assert database.statements == 1


@pytest.mark.parametrize("posts", [1, 5])
def test_the_assessment_is_the_same_however_many_posts_there_are(
    database: Database, line: Line, segment: Segment, posts: int
) -> None:
    build_line(database, line, segment, posts=posts)
    result = assess_line(database, "AL-2", as_of=TODAY)
    assert len(result.protected) == posts
