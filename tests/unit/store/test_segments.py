from __future__ import annotations

import dataclasses

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.model.enums import CoatingType
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository


@pytest.fixture
def segments(database: Database, line: Line) -> SegmentRepository:
    LineRepository(database).add(line)
    return SegmentRepository(database)


def span(start: float, end: float) -> StationRange:
    return StationRange(Station(start), Station(end))


def test_a_segment_survives_a_round_trip(segments: SegmentRepository, segment: Segment) -> None:
    segments.add(segment)
    assert segments.get("AL-2-004") == segment


def test_an_optional_resistivity_comes_back_as_none(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(segment)
    assert segments.get("AL-2-004").soil_resistivity_ohm_m is None


def test_a_measured_resistivity_comes_back_as_a_number(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(dataclasses.replace(segment, soil_resistivity_ohm_m=14.5))
    assert segments.get("AL-2-004").soil_resistivity_ohm_m == pytest.approx(14.5)


def test_two_segments_that_share_pipe_are_refused(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(segment)
    clash = dataclasses.replace(segment, code="AL-2-005", extent=span(1100.0, 2000.0))
    with pytest.raises(ConflictError) as caught:
        segments.add(clash)
    assert caught.value.detail["clashes_with"] == ["AL-2-004"]


def test_an_overlap_can_be_forced_through_when_a_line_is_being_resegmented(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(segment)
    clash = dataclasses.replace(segment, code="AL-2-005", extent=span(1100.0, 2000.0))
    segments.add(clash, allow_overlap=True)
    assert segments.count() == 2


def test_segments_that_only_touch_at_a_station_still_clash(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(segment)
    butted = dataclasses.replace(segment, code="AL-2-005", extent=span(1200.0, 2000.0))
    with pytest.raises(ConflictError):
        segments.add(butted)


def test_a_segment_on_another_line_never_clashes(
    database: Database, segments: SegmentRepository, segment: Segment, line: Line
) -> None:
    LineRepository(database).add(dataclasses.replace(line, code="BR-9"))
    segments.add(segment)
    segments.add(dataclasses.replace(segment, code="BR-9-001", line_code="BR-9"))
    assert segments.count() == 2


def test_segments_of_a_line_come_back_in_stationing_order(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(dataclasses.replace(segment, code="C", extent=span(2400.0, 3000.0)))
    segments.add(dataclasses.replace(segment, code="A", extent=span(0.0, 1200.0)))
    segments.add(dataclasses.replace(segment, code="B", extent=span(1200.1, 2399.0)))
    assert [item.code for item in segments.for_line("AL-2")] == ["A", "B", "C"]


def test_covering_finds_the_segment_a_station_falls_on(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(segment)
    assert [s.code for s in segments.covering("AL-2", Station(600.0))] == ["AL-2-004"]
    assert segments.covering("AL-2", Station(1600.0)) == []


def test_covering_includes_both_ends_of_a_segment(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(segment)
    assert segments.covering("AL-2", Station(0.0))
    assert segments.covering("AL-2", Station(1200.0))


def test_a_segment_never_overlaps_itself(segments: SegmentRepository, segment: Segment) -> None:
    segments.add(segment)
    assert segments.overlapping(segment) == []


def test_all_orders_by_line_then_station(
    database: Database, segments: SegmentRepository, segment: Segment, line: Line
) -> None:
    LineRepository(database).add(dataclasses.replace(line, code="BR-9"))
    segments.add(dataclasses.replace(segment, code="B1", line_code="BR-9"))
    segments.add(segment)
    assert [item.code for item in segments.all()] == ["AL-2-004", "B1"]


def test_a_missing_segment_is_named_in_the_refusal(segments: SegmentRepository) -> None:
    assert segments.find("AL-2-004") is None
    with pytest.raises(NotFoundError) as caught:
        segments.get("AL-2-004")
    assert caught.value.detail["code"] == "AL-2-004"


def test_deleting_a_segment_removes_it(segments: SegmentRepository, segment: Segment) -> None:
    segments.add(segment)
    segments.delete("AL-2-004")
    assert segments.count() == 0
    with pytest.raises(NotFoundError):
        segments.delete("AL-2-004")


def test_deleting_a_line_takes_its_segments_with_it(
    database: Database, segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(segment)
    LineRepository(database).delete("AL-2")
    assert segments.count() == 0


def test_the_coating_comes_back_as_an_enum(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP))
    assert segments.get("AL-2-004").coating is CoatingType.TAPE_WRAP
