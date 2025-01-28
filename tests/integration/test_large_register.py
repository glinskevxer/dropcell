"""A register big enough that anything quadratic in it shows up.

Two hundred posts with five readings each is a small line by the standards of
the trade and it is more than enough to catch the failure this suite exists for,
which is a report that walks the posts and queries inside the loop. Those run
fine on the handful of records a unit test builds and are unusable on a real
register, and the only way to see it is to build one.

Everything here asserts on counts and on statements rather than on wall clock.
A timing assertion fails on a busy machine and passes on a slow implementation
that happens to run on a fast one, and neither of those is the question.
"""

from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.coverage import coverage
from dropcell.analysis.line import assess_line
from dropcell.analysis.schedule import line_histories
from dropcell.model.enums import (
    ClassLocation,
    CoatingType,
    Commodity,
    LeadKind,
    ProtectionMethod,
)
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.report.protection import render_protection
from dropcell.schedule.policy import STANDARD_POLICY
from dropcell.schedule.register import build_register
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.migrations import migrate
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository

POSTS = 200
READINGS_PER_POST = 5
TODAY = dt.date(2025, 3, 14)


def build(posts: int) -> Database:
    """A line with that many posts, each read once a year for five years."""
    database = Database(":memory:")
    migrate(database)
    length = posts * 100.0 + 100.0
    LineRepository(database).add(
        Line(
            code="AL-2",
            name="Ashfield lateral",
            operator="Northmoor Gas",
            commodity=Commodity.NATURAL_GAS,
            length_m=length,
            nominal_diameter_mm=323.9,
            installed_year=1974,
        )
    )
    SegmentRepository(database).add(
        Segment(
            code="AL-2-001",
            line_code="AL-2",
            extent=StationRange(Station(0.0), Station(length)),
            coating=CoatingType.COAL_TAR,
            protection=ProtectionMethod.IMPRESSED_CURRENT,
            class_location=ClassLocation.RURAL,
            outside_diameter_mm=323.9,
            wall_thickness_mm=6.35,
            installed_year=1974,
        )
    )
    point_store = TestPointRepository(database)
    readings = ReadingRepository(database)
    batch: list[Reading] = []
    for index in range(posts):
        code = f"TP-{index:04d}"
        point_store.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(float(index) * 100.0),
                leads=frozenset({LeadKind.PIPE}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
        for year in range(2021, 2021 + READINGS_PER_POST):
            batch.append(
                Reading(
                    test_point_code=code,
                    lead=LeadKind.PIPE,
                    taken_on=dt.date(year, 3, 14),
                    on_mv=-1120.0,
                    off_mv=-905.0 if index % 7 else -780.0,
                )
            )
    readings.add_many(batch)
    return database


@pytest.fixture(scope="module")
def big() -> Database:
    return build(POSTS)


def test_the_register_holds_what_was_put_in_it(big: Database) -> None:
    assert TestPointRepository(big).count() == POSTS
    assert ReadingRepository(big).count() == POSTS * READINGS_PER_POST


def test_assessing_the_line_costs_the_same_as_assessing_a_small_one(
    big: Database,
) -> None:
    small = build(4)
    small.statements = 0
    assess_line(small, "AL-2", as_of=TODAY)
    cost_of_four = small.statements

    big.statements = 0
    result = assess_line(big, "AL-2", as_of=TODAY)
    assert len(result.posts) == POSTS
    assert big.statements == cost_of_four


def test_every_post_is_judged_on_its_most_recent_reading(big: Database) -> None:
    result = assess_line(big, "AL-2", as_of=TODAY)
    assert all(item.reading is not None for item in result.posts)
    assert {item.reading.taken_on.year for item in result.posts if item.reading} == {2025}


def test_the_failing_posts_are_the_ones_that_were_built_to_fail(
    big: Database,
) -> None:
    result = assess_line(big, "AL-2", as_of=TODAY)
    failing = {item.code for item in result.under_criterion}
    assert len(failing) == len([index for index in range(POSTS) if index % 7 == 0])


def test_the_protection_report_renders_on_a_line_this_size(big: Database) -> None:
    rendered = render_protection(assess_line(big, "AL-2", as_of=TODAY))
    assert f"{POSTS} posts" in rendered
    assert "Under criterion" in rendered


def test_the_coverage_report_walks_the_whole_line(big: Database) -> None:
    line = LineRepository(big).get("AL-2")
    posts = TestPointRepository(big).for_line("AL-2")
    segments = SegmentRepository(big).for_line("AL-2")
    report = coverage(line, segments, posts, reach_m=400.0)
    assert report.posts == POSTS
    assert report.covered_share > 0.5


def test_the_monitoring_register_covers_every_post(big: Database) -> None:
    histories = line_histories(big, "AL-2")
    assert len(histories) == POSTS
    register = build_register(STANDARD_POLICY, histories, as_of=TODAY)
    assert len(register) == POSTS
    assert all(item.ever_visited for item in register)


def test_the_history_of_one_post_is_the_readings_it_was_given(big: Database) -> None:
    history = ReadingRepository(big).for_point("TP-0001")
    assert len(history) == READINGS_PER_POST
    assert [reading.taken_on.year for reading in history] == sorted(
        reading.taken_on.year for reading in history
    )
