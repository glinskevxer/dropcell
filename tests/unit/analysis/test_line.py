from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.line import assess_line
from dropcell.errors import NotFoundError
from dropcell.model.enums import LeadKind, ProtectionMethod
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.model.testpoint import Reading, TestPoint
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
    database: Database,
    code: str,
    *,
    off_mv: float | None = -905.0,
    taken_on: dt.date = TODAY,
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


def test_a_line_with_no_posts_is_refused(register: Database) -> None:
    with pytest.raises(NotFoundError):
        assess_line(register, "AL-2", as_of=TODAY)


def test_a_line_that_is_not_there_is_refused(register: Database) -> None:
    with pytest.raises(NotFoundError):
        assess_line(register, "ZZ-9", as_of=TODAY)


def test_a_protected_post_counts_as_protected(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1")
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert len(result.protected) == 1
    assert result.protection_rate == pytest.approx(1.0)


def test_a_post_short_of_the_criterion_is_counted_against(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", off_mv=-780.0)
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert len(result.under_criterion) == 1
    assert result.protection_rate == pytest.approx(0.0)
    assert result.posts[0].has_findings


def test_a_post_that_has_never_been_read_is_its_own_category(
    register: Database,
) -> None:
    add_post(register, "TP-1", 600.0)
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert len(result.unread) == 1
    assert result.assessed == ()
    assert result.protection_rate == pytest.approx(0.0)


def test_an_old_reading_is_still_judged_and_flagged_as_stale(
    register: Database,
) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", taken_on=dt.date(2022, 1, 1))
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert len(result.protected) == 1
    assert len(result.stale) == 1
    assert result.posts[0].reading_age_days is not None


def test_a_recent_reading_is_not_stale(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", taken_on=dt.date(2024, 12, 1))
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert result.stale == ()


def test_a_post_off_the_end_of_every_segment_cannot_be_judged(
    register: Database,
) -> None:
    add_post(register, "TP-9", 9000.0)
    add_reading(register, "TP-9")
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert len(result.off_segment) == 1
    assert result.posts[0].verdict is None
    assert result.assessed == ()


def test_the_criterion_set_chosen_is_reported(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1")
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert result.posts[0].criterion_set == "impressed_current"


def test_a_galvanic_segment_gets_the_galvanic_set(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(
        dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    )
    add_post(database, "TP-1", 600.0)
    add_reading(database, "TP-1")
    result = assess_line(database, "AL-2", as_of=TODAY)
    assert result.posts[0].criterion_set == "galvanic"


def test_the_latest_reading_is_the_one_judged(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", off_mv=-780.0, taken_on=dt.date(2024, 1, 1))
    add_reading(register, "TP-1", off_mv=-905.0, taken_on=TODAY)
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert result.posts[0].protected


def test_posts_come_back_in_stationing_order(register: Database) -> None:
    add_post(register, "TP-2", 900.0)
    add_post(register, "TP-1", 100.0)
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert [item.code for item in result.posts] == ["TP-1", "TP-2"]


def test_the_rate_is_over_the_posts_that_could_be_judged(register: Database) -> None:
    add_post(register, "TP-1", 100.0)
    add_post(register, "TP-2", 600.0)
    add_post(register, "TP-3", 900.0)
    add_reading(register, "TP-1")
    add_reading(register, "TP-2", off_mv=-780.0)
    result = assess_line(register, "AL-2", as_of=TODAY)
    assert len(result.unread) == 1
    assert result.protection_rate == pytest.approx(0.5)


def test_the_summary_names_the_line_and_the_counts(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1")
    assert (
        "AL-2: 1 of 1 posts protected" in assess_line(register, "AL-2", as_of=TODAY).summary()
    )


def test_a_casing_lead_can_be_assessed_instead(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1")
    result = assess_line(register, "AL-2", as_of=TODAY, lead=LeadKind.CASING)
    assert len(result.unread) == 1
