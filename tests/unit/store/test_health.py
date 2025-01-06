from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.model.coupon import STANDARD_AREA_M2, Coupon
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station, StationRange
from dropcell.store.coupons import CouponRepository
from dropcell.store.database import Database
from dropcell.store.health import Severity, check_register, worst
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository


def add_post(database: Database, code: str, metres: float, leads: set[LeadKind]) -> None:
    TestPointRepository(database).add(
        TestPoint(
            code=code,
            line_code="AL-2",
            station=Station(metres),
            leads=frozenset(leads),
            installed_on=dt.date(1998, 5, 4),
        )
    )


def test_an_empty_register_has_nothing_wrong_with_it(database: Database) -> None:
    assert check_register(database) == []
    assert worst([]) is None


def test_a_line_with_no_segments_is_an_error(database: Database, line: Line) -> None:
    LineRepository(database).add(line)
    found = check_register(database)
    assert [item.check for item in found] == ["line has no segments"]
    assert found[0].severity is Severity.ERROR


def test_a_fully_described_line_reports_no_gap(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(
        dataclasses.replace(segment, extent=StationRange(Station(0.0), Station(line.length_m)))
    )
    assert check_register(database) == []


def test_a_partly_described_line_reports_the_stretch_that_is_not(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    found = [
        item for item in check_register(database) if item.check == "gap in the segmentation"
    ]
    assert len(found) == 1
    assert "to the end of the line" in found[0].detail
    assert found[0].severity is Severity.NOTE


def test_a_gap_at_the_start_of_a_line_is_reported(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(
        dataclasses.replace(
            segment, extent=StationRange(Station(400.0), Station(line.length_m))
        )
    )
    found = [
        item for item in check_register(database) if item.check == "gap in the segmentation"
    ]
    assert "0 m to 400 m" in found[0].detail


def test_a_post_off_every_segment_is_a_warning(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    add_post(database, "TP-9", 9000.0, {LeadKind.PIPE})
    found = [
        item for item in check_register(database) if item.check == "post off every segment"
    ]
    assert found[0].subject == "TP-9"
    assert found[0].severity is Severity.WARNING


def test_a_post_on_a_line_with_no_segments_is_not_reported_twice(
    database: Database, line: Line
) -> None:
    LineRepository(database).add(line)
    add_post(database, "TP-9", 9000.0, {LeadKind.PIPE})
    checks = {item.check for item in check_register(database)}
    assert checks == {"line has no segments"}


def test_a_coupon_on_a_post_with_no_coupon_lead_is_a_warning(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    add_post(database, "TP-1", 600.0, {LeadKind.PIPE})
    CouponRepository(database).add(
        Coupon(
            code="CP-4",
            test_point_code="TP-1",
            area_m2=STANDARD_AREA_M2,
            shunt_ohm=0.01,
            installed_on=dt.date(2019, 6, 3),
        )
    )
    found = [
        item for item in check_register(database) if item.check == "coupon with no coupon lead"
    ]
    assert found[0].subject == "CP-4"


def test_a_coupon_on_a_post_that_carries_one_is_fine(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    add_post(database, "TP-1", 600.0, {LeadKind.PIPE, LeadKind.COUPON})
    CouponRepository(database).add(
        Coupon(
            code="CP-4",
            test_point_code="TP-1",
            area_m2=STANDARD_AREA_M2,
            shunt_ohm=0.01,
            installed_on=dt.date(2019, 6, 3),
        )
    )
    checks = {item.check for item in check_register(database)}
    assert "coupon with no coupon lead" not in checks


def test_an_off_more_negative_than_its_on_is_a_warning(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    add_post(database, "TP-1", 600.0, {LeadKind.PIPE})
    ReadingRepository(database).add(
        Reading(
            test_point_code="TP-1",
            lead=LeadKind.PIPE,
            taken_on=dt.date(2025, 3, 14),
            on_mv=-905.0,
            off_mv=-1120.0,
        )
    )
    found = [
        item for item in check_register(database) if item.check == "off more negative than on"
    ]
    assert found[0].subject == "TP-1"


def test_a_sensible_pair_is_not_reported(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    add_post(database, "TP-1", 600.0, {LeadKind.PIPE})
    ReadingRepository(database).add(
        Reading(
            test_point_code="TP-1",
            lead=LeadKind.PIPE,
            taken_on=dt.date(2025, 3, 14),
            on_mv=-1120.0,
            off_mv=-905.0,
        )
    )
    checks = {item.check for item in check_register(database)}
    assert "off more negative than on" not in checks


def test_findings_come_back_worst_first(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    add_post(database, "TP-9", 9000.0, {LeadKind.PIPE})
    found = check_register(database)
    ranks = [item.severity.rank for item in found]
    assert ranks == sorted(ranks, reverse=True)
    assert worst(found) is Severity.WARNING


def test_a_finding_renders_on_one_line(database: Database, line: Line) -> None:
    LineRepository(database).add(line)
    rendered = check_register(database)[0].render()
    assert "error" in rendered
    assert "AL-2" in rendered


@pytest.mark.parametrize(
    ("lower", "higher"),
    [(Severity.NOTE, Severity.WARNING), (Severity.WARNING, Severity.ERROR)],
)
def test_the_severities_are_ordered(lower: Severity, higher: Severity) -> None:
    assert lower.rank < higher.rank
