from __future__ import annotations

import dataclasses

import pytest

from dropcell.errors import NotFoundError, ValidationError
from dropcell.model.enums import CoatingType
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository


@pytest.fixture
def segments(database: Database, line: Line, segment: Segment) -> SegmentRepository:
    LineRepository(database).add(line)
    store = SegmentRepository(database)
    store.add(segment)
    return store


def test_a_segment_splits_into_two_halves(segments: SegmentRepository) -> None:
    left, right = segments.split("AL-2-004", Station(400.0))
    assert left.code == "AL-2-004-A"
    assert right.code == "AL-2-004-B"
    assert left.length_m == pytest.approx(400.0, abs=0.02)
    assert right.length_m == pytest.approx(800.0)
    assert left.extent.end.metres < right.extent.start.metres


def test_the_original_is_gone(segments: SegmentRepository) -> None:
    segments.split("AL-2-004", Station(400.0))
    with pytest.raises(NotFoundError):
        segments.get("AL-2-004")
    assert segments.count() == 2


def test_the_halves_inherit_everything_else(
    segments: SegmentRepository, segment: Segment
) -> None:
    left, right = segments.split("AL-2-004", Station(400.0))
    for half in (left, right):
        assert half.coating is segment.coating
        assert half.protection is segment.protection
        assert half.class_location is segment.class_location
        assert half.installed_year == segment.installed_year


def test_the_codes_can_be_given(segments: SegmentRepository) -> None:
    left, right = segments.split(
        "AL-2-004", Station(400.0), left_code="AL-2-004", right_code="AL-2-006"
    )
    assert left.code == "AL-2-004"
    assert right.code == "AL-2-006"


def test_two_halves_with_the_same_code_are_refused(
    segments: SegmentRepository,
) -> None:
    with pytest.raises(ValidationError):
        segments.split("AL-2-004", Station(400.0), left_code="X", right_code="X")


def test_splitting_off_the_segment_is_refused(segments: SegmentRepository) -> None:
    with pytest.raises(ValidationError):
        segments.split("AL-2-004", Station(9000.0))


def test_splitting_at_an_end_is_refused(segments: SegmentRepository) -> None:
    with pytest.raises(ValidationError):
        segments.split("AL-2-004", Station(0.0))
    with pytest.raises(ValidationError):
        segments.split("AL-2-004", Station(1200.0))


def test_the_boundary_station_belongs_to_the_second_half(
    segments: SegmentRepository,
) -> None:
    left, right = segments.split("AL-2-004", Station(400.0))
    assert right.contains(Station(400.0))
    assert not left.contains(Station(400.0))


def test_splitting_a_segment_that_is_not_there_is_refused(
    segments: SegmentRepository,
) -> None:
    with pytest.raises(NotFoundError):
        segments.split("AL-2-009", Station(400.0))


def test_the_halves_do_not_overlap_anything(
    segments: SegmentRepository, segment: Segment
) -> None:
    segments.add(
        dataclasses.replace(
            segment,
            code="AL-2-005",
            extent=dataclasses.replace(
                segment.extent, start=Station(1200.1), end=Station(2000.0)
            ),
        )
    )
    left, right = segments.split("AL-2-004", Station(400.0))
    assert segments.overlapping(left) == []
    assert segments.overlapping(right) == []


def test_a_change_can_be_set_on_one_half_afterwards(
    segments: SegmentRepository,
) -> None:
    left, right = segments.split("AL-2-004", Station(400.0))
    segments.delete(right.code)
    segments.add(dataclasses.replace(right, coating=CoatingType.THREE_LAYER_PE))
    assert segments.get(left.code).coating is CoatingType.COAL_TAR
    assert segments.get(right.code).coating is CoatingType.THREE_LAYER_PE


def test_the_two_halves_add_up_to_the_original(
    segments: SegmentRepository, segment: Segment
) -> None:
    left, right = segments.split("AL-2-004", Station(400.0))
    assert left.length_m + right.length_m == pytest.approx(segment.length_m, abs=0.02)
