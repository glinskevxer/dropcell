from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.line import assess_line
from dropcell.config import Settings
from dropcell.model.enums import CoatingType, LeadKind
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


def build(database: Database, line: Line, segment: Segment, off_mv: float) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    TestPointRepository(database).add(
        TestPoint(
            code="TP-1",
            line_code="AL-2",
            station=Station(600.0),
            leads=frozenset({LeadKind.PIPE}),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    ReadingRepository(database).add(
        Reading(
            test_point_code="TP-1",
            lead=LeadKind.PIPE,
            taken_on=TODAY,
            on_mv=-1120.0,
            off_mv=off_mv,
        )
    )


def test_no_settings_means_the_figures_in_the_standards(
    database: Database, line: Line, segment: Segment
) -> None:
    build(database, line, segment, -905.0)
    result = assess_line(database, "AL-2", as_of=TODAY)
    assert result.protection_rate == pytest.approx(1.0)


def test_a_tighter_criterion_changes_the_verdict(
    database: Database, line: Line, segment: Segment
) -> None:
    build(database, line, segment, -905.0)
    tight = assess_line(database, "AL-2", as_of=TODAY, settings=Settings(protection_mv=-950.0))
    assert tight.protection_rate == pytest.approx(0.0)
    assert len(tight.under_criterion) == 1


def test_a_looser_criterion_changes_it_the_other_way(
    database: Database, line: Line, segment: Segment
) -> None:
    build(database, line, segment, -800.0)
    assert assess_line(database, "AL-2", as_of=TODAY).protection_rate == pytest.approx(0.0)
    loose = assess_line(database, "AL-2", as_of=TODAY, settings=Settings(protection_mv=-780.0))
    assert loose.protection_rate == pytest.approx(1.0)


def test_a_moved_over_protection_limit_still_applies(
    database: Database, line: Line, segment: Segment
) -> None:
    build(database, line, segment, -1420.0)
    result = assess_line(database, "AL-2", as_of=TODAY)
    assert result.posts[0].protected
    assert result.posts[0].has_findings


def test_the_criterion_set_name_is_unchanged_by_the_settings(
    database: Database, line: Line, segment: Segment
) -> None:
    build(database, line, segment, -905.0)
    result = assess_line(database, "AL-2", as_of=TODAY, settings=Settings(protection_mv=-950.0))
    assert result.posts[0].criterion_set == "impressed_current"


def test_a_shielding_coating_is_still_a_shielding_coating(
    database: Database, line: Line, segment: Segment
) -> None:
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    build(database, line, taped, -905.0)
    result = assess_line(database, "AL-2", as_of=TODAY, settings=Settings(protection_mv=-950.0))
    assert result.posts[0].segment is not None
    assert result.posts[0].segment.needs_above_ground_survey
