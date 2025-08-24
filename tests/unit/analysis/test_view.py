from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.view import gather
from dropcell.config import Settings
from dropcell.errors import NotFoundError
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
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


def add_reading(database: Database, code: str, off_mv: float) -> None:
    ReadingRepository(database).add(
        Reading(
            test_point_code=code,
            lead=LeadKind.PIPE,
            taken_on=TODAY,
            on_mv=-1120.0,
            off_mv=off_mv,
        )
    )


def test_a_line_with_no_posts_gets_no_assessment(register: Database) -> None:
    view = gather(register, "AL-2", as_of=TODAY)
    assert not view.has_posts
    assert view.assessment is None
    assert view.judged == 0
    assert view.protection_rate == pytest.approx(0.0)


def test_a_line_with_no_posts_is_not_an_error(register: Database) -> None:
    view = gather(register, "AL-2", as_of=TODAY)
    assert view.line.code == "AL-2"
    assert view.segments


def test_a_line_that_is_not_there_is_an_error(register: Database) -> None:
    with pytest.raises(NotFoundError):
        gather(register, "ZZ-9", as_of=TODAY)


def test_a_read_line_carries_its_assessment(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    view = gather(register, "AL-2", as_of=TODAY)
    assert view.judged == 1
    assert view.protected == 1
    assert view.protection_rate == pytest.approx(1.0)


def test_the_unread_posts_are_counted(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_post(register, "TP-2", 900.0)
    add_reading(register, "TP-1", -905.0)
    assert gather(register, "AL-2", as_of=TODAY).unread == 1


def test_the_settings_reach_the_assessment(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    ordinary = gather(register, "AL-2", as_of=TODAY)
    tight = gather(register, "AL-2", as_of=TODAY, settings=Settings(protection_mv=-950.0))
    assert ordinary.protection_rate == pytest.approx(1.0)
    assert tight.protection_rate == pytest.approx(0.0)


def test_the_settings_reach_the_coverage_too(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    wide = gather(register, "AL-2", as_of=TODAY)
    narrow = gather(register, "AL-2", as_of=TODAY, settings=Settings(post_reach_m=100.0))
    assert wide.coverage.covered_share > narrow.coverage.covered_share


def test_the_monitoring_register_is_gathered(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    view = gather(register, "AL-2", as_of=TODAY)
    assert [item.asset_code for item in view.register] == ["TP-1"]
    assert view.overdue


def test_a_post_read_today_is_not_overdue(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    assert gather(register, "AL-2", as_of=TODAY).overdue == ()


def test_the_findings_are_gathered_and_split(register: Database) -> None:
    from dropcell.findings.finding import Finding, FindingKind, FindingState
    from dropcell.stationing import StationRange
    from dropcell.store.findings import FindingRepository

    findings = FindingRepository(register)
    findings.raise_finding(
        Finding(
            code="F-2025-001",
            line_code="AL-2",
            kind=FindingKind.UNDER_CRITERION,
            raised_on=TODAY,
            extent=StationRange(Station(600.0), Station(660.0)),
            summary="under criterion",
        )
    )
    findings.move("F-2025-001", FindingState.CLEARED, on=TODAY)
    view = gather(register, "AL-2", as_of=TODAY)
    assert len(view.findings) == 1
    assert view.open_findings == ()


def test_everything_is_gathered_in_one_call(register: Database) -> None:
    add_post(register, "TP-1", 600.0)
    add_reading(register, "TP-1", -905.0)
    view = gather(register, "AL-2", as_of=TODAY)
    assert view.line.code == "AL-2"
    assert view.segments
    assert view.posts
    assert view.assessment is not None
    assert view.register
    assert view.coverage.posts == 1
