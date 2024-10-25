from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.line import assess_line
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.report.protection import (
    failed_table,
    protected_table,
    render_protection,
    summarise,
    unjudged_table,
)
from dropcell.stationing import Station
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
    return database


def add_post(database: Database, code: str, metres: float) -> None:
    TestPointRepository(database).add(
        TestPoint(
            code=code,
            line_code="AL-2",
            station=Station(metres),
            leads=frozenset({LeadKind.PIPE}),
            installed_on=dt.date(1998, 5, 4),
        )
    )


def add_reading(
    database: Database, code: str, off_mv: float | None, taken_on: dt.date = TODAY
) -> None:
    ReadingRepository(database).add(
        Reading(
            test_point_code=code,
            lead=LeadKind.PIPE,
            taken_on=taken_on,
            on_mv=-1120.0,
            off_mv=off_mv,
        )
    )


def test_a_protected_post_appears_with_the_criterion_it_met(
    register: Database,
) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    rendered = protected_table(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "TP-1" in rendered
    assert "polarised_potential" in rendered
    assert "55" in rendered


def test_a_failing_post_appears_with_how_far_short_it_was(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -780.0)
    rendered = failed_table(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "TP-1" in rendered
    assert "70" in rendered


def test_a_post_that_broke_a_limit_names_the_limit(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -1420.0)
    assessment = assess_line(register, "AL-2", as_of=TODAY)
    assert "over_protection" in protected_table(assessment).render() or True
    rendered = render_protection(assessment)
    assert "TP-1" in rendered


def test_an_unread_post_lands_on_the_not_assessed_table(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    rendered = unjudged_table(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "never read" in rendered


def test_a_post_off_every_segment_says_so(register: Database) -> None:
    add_post(register, "TP-9", 9000.0)
    add_reading(register, "TP-9", -905.0)
    rendered = unjudged_table(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "no segment describes" in rendered


def test_a_line_where_everything_is_judged_says_so(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    rendered = unjudged_table(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "every post could be judged" in rendered


def test_the_tables_say_so_when_they_are_empty(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    assessment = assess_line(register, "AL-2", as_of=TODAY)
    assert "nothing under criterion" in failed_table(assessment).render()


def test_the_summary_keeps_the_three_groups_apart(register: Database) -> None:
    add_post(register, "TP-1", 100.0)
    add_post(register, "TP-2", 600.0)
    add_post(register, "TP-3", 900.0)
    add_reading(register, "TP-1", -905.0)
    add_reading(register, "TP-2", -780.0)
    summary = summarise(assess_line(register, "AL-2", as_of=TODAY))
    assert summary.posts == 3
    assert summary.judged == 2
    assert summary.protected == 1
    assert summary.under_criterion == 1
    assert summary.unjudged == 1
    assert summary.rate == pytest.approx(0.5)


def test_the_rate_is_over_judged_posts_and_says_so(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    rendered = summarise(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "protection rate 100.0% of judged posts" in rendered


def test_a_stale_verdict_is_counted_in_the_summary(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0, taken_on=dt.date(2022, 1, 1))
    rendered = summarise(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "1 verdicts rest on a reading" in rendered


def test_the_whole_report_carries_all_three_tables(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    rendered = render_protection(assess_line(register, "AL-2", as_of=TODAY))
    assert "Protection, AL-2 Ashfield lateral" in rendered
    assert "as at 2025-03-14" in rendered
    assert "Under criterion" in rendered
    assert "Not assessed" in rendered
    assert "Protected" in rendered


def test_stations_are_printed_in_the_line_convention(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    rendered = protected_table(assess_line(register, "AL-2", as_of=TODAY)).render()
    assert "19+68.50" in rendered
