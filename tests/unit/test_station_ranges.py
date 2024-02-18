from __future__ import annotations

import pytest

from dropcell.errors import StationError
from dropcell.stationing import Convention, Station, StationRange, merge_ranges, total_length_m


def rng(start: float, end: float) -> StationRange:
    return StationRange(Station(start), Station(end))


def test_a_range_knows_how_much_line_it_covers() -> None:
    assert rng(100.0, 250.0).length_m == pytest.approx(150.0)


def test_a_range_of_zero_length_is_allowed() -> None:
    assert rng(100.0, 100.0).length_m == pytest.approx(0.0)


def test_a_backwards_range_is_refused() -> None:
    with pytest.raises(StationError) as caught:
        rng(250.0, 100.0)
    assert caught.value.detail["start"] == pytest.approx(250.0)


def test_parsing_accepts_the_two_spellings_a_dig_sheet_uses() -> None:
    assert StationRange.parse("12+00.00 to 14+50.00").length_m == pytest.approx(250 * 0.3048)
    assert StationRange.parse("12+00.00 - 14+50.00").length_m == pytest.approx(250 * 0.3048)


def test_parsing_a_metric_range_uses_the_metric_convention() -> None:
    parsed = StationRange.parse("1+000.0 to 1+250.0", Convention.METRIC)
    assert parsed.length_m == pytest.approx(250.0)


def test_parsing_junk_raises() -> None:
    with pytest.raises(StationError):
        StationRange.parse("12+00.00")


def test_containment_includes_both_endpoints() -> None:
    span = rng(100.0, 200.0)
    assert span.contains(Station(100.0))
    assert span.contains(Station(150.0))
    assert span.contains(Station(200.0))
    assert not span.contains(Station(99.9))
    assert not span.contains(Station(200.1))


def test_ranges_that_only_touch_still_count_as_overlapping() -> None:
    assert rng(100.0, 200.0).overlaps(rng(200.0, 300.0))
    assert not rng(100.0, 200.0).overlaps(rng(200.1, 300.0))


def test_intersection_is_the_shared_piece() -> None:
    shared = rng(100.0, 200.0).intersection(rng(150.0, 400.0))
    assert shared == rng(150.0, 200.0)


def test_intersection_of_disjoint_ranges_is_nothing() -> None:
    assert rng(100.0, 200.0).intersection(rng(300.0, 400.0)) is None


def test_subtracting_a_middle_piece_leaves_two_ranges() -> None:
    left, right = rng(0.0, 300.0).subtract(rng(100.0, 200.0))
    assert left == rng(0.0, 100.0)
    assert right == rng(200.0, 300.0)


def test_subtracting_an_end_piece_leaves_one_range() -> None:
    assert rng(0.0, 300.0).subtract(rng(200.0, 500.0)) == [rng(0.0, 200.0)]
    assert rng(0.0, 300.0).subtract(rng(-50.0, 100.0)) == [rng(100.0, 300.0)]


def test_subtracting_everything_leaves_nothing() -> None:
    assert rng(0.0, 300.0).subtract(rng(-10.0, 400.0)) == []


def test_subtracting_a_disjoint_range_changes_nothing() -> None:
    assert rng(0.0, 300.0).subtract(rng(400.0, 500.0)) == [rng(0.0, 300.0)]


def test_merging_joins_overlapping_ranges() -> None:
    merged = merge_ranges([rng(0.0, 100.0), rng(50.0, 200.0)])
    assert merged == [rng(0.0, 200.0)]


def test_merging_leaves_a_real_gap_alone() -> None:
    merged = merge_ranges([rng(0.0, 100.0), rng(140.0, 200.0)])
    assert merged == [rng(0.0, 100.0), rng(140.0, 200.0)]


def test_a_gap_inside_the_tolerance_is_bridged() -> None:
    merged = merge_ranges([rng(0.0, 100.0), rng(140.0, 200.0)], gap_tolerance_m=40.0)
    assert merged == [rng(0.0, 200.0)]


def test_a_gap_just_over_the_tolerance_is_not_bridged() -> None:
    merged = merge_ranges([rng(0.0, 100.0), rng(140.1, 200.0)], gap_tolerance_m=40.0)
    assert len(merged) == 2


def test_merging_swallows_a_range_wholly_inside_another() -> None:
    merged = merge_ranges([rng(0.0, 300.0), rng(100.0, 150.0)])
    assert merged == [rng(0.0, 300.0)]


def test_merging_sorts_before_it_joins() -> None:
    merged = merge_ranges([rng(200.0, 300.0), rng(0.0, 100.0), rng(90.0, 210.0)])
    assert merged == [rng(0.0, 300.0)]


def test_merging_nothing_gives_nothing() -> None:
    assert merge_ranges([]) == []


def test_a_negative_tolerance_is_refused() -> None:
    with pytest.raises(StationError):
        merge_ranges([rng(0.0, 100.0)], gap_tolerance_m=-1.0)


def test_total_length_counts_shared_line_once() -> None:
    assert total_length_m([rng(0.0, 100.0), rng(50.0, 200.0)]) == pytest.approx(200.0)
    assert total_length_m([rng(0.0, 100.0), rng(200.0, 250.0)]) == pytest.approx(150.0)
