from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.coverage import (
    coverage,
    find_gaps,
    segments_without_posts,
    shielded_reach,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import CoatingType, LeadKind
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station, StationRange


def post(code: str, metres: float) -> TestPoint:
    return TestPoint(
        code=code,
        line_code="AL-2",
        station=Station(metres),
        leads=frozenset({LeadKind.PIPE}),
        installed_on=dt.date(1998, 5, 4),
    )


def test_a_line_with_no_posts_is_one_long_gap(line: Line) -> None:
    gaps = find_gaps(line, [])
    assert len(gaps) == 1
    assert gaps[0].length_m == pytest.approx(line.length_m)
    assert gaps[0].at_an_end


def test_a_post_covers_the_reach_either_side_of_itself(line: Line) -> None:
    gaps = find_gaps(line, [post("TP-1", 1600.0)], reach_m=1600.0)
    assert len(gaps) == 1
    assert gaps[0].extent.start == Station(3200.0)
    assert gaps[0].before == "TP-1"
    assert gaps[0].after is None


def test_two_posts_inside_a_reach_of_each_other_leave_no_middle_gap(
    line: Line,
) -> None:
    gaps = find_gaps(line, [post("TP-1", 1600.0), post("TP-2", 4000.0)], reach_m=1600.0)
    assert all(gap.at_an_end for gap in gaps)


def test_two_posts_far_apart_leave_a_gap_between_them(line: Line) -> None:
    gaps = find_gaps(line, [post("TP-1", 1600.0), post("TP-2", 9000.0)], reach_m=1600.0)
    middle = [gap for gap in gaps if not gap.at_an_end]
    assert len(middle) == 1
    assert middle[0].before == "TP-1"
    assert middle[0].after == "TP-2"
    assert middle[0].length_m == pytest.approx(9000.0 - 1600.0 - 3200.0)


def test_posts_are_sorted_before_the_gaps_are_worked_out(line: Line) -> None:
    forward = find_gaps(line, [post("TP-1", 1600.0), post("TP-2", 9000.0)])
    backward = find_gaps(line, [post("TP-2", 9000.0), post("TP-1", 1600.0)])
    assert forward == backward


def test_a_post_at_the_origin_covers_the_start(line: Line) -> None:
    gaps = find_gaps(line, [post("TP-1", 0.0)], reach_m=1600.0)
    assert gaps[0].before == "TP-1"


def test_a_reach_of_nothing_is_refused(line: Line) -> None:
    with pytest.raises(ValidationError):
        find_gaps(line, [], reach_m=0.0)


def test_a_segment_with_a_post_on_it_is_covered(segment: Segment) -> None:
    assert segments_without_posts([segment], [post("TP-1", 600.0)]) == []


def test_a_segment_with_no_post_on_it_is_named(segment: Segment) -> None:
    assert segments_without_posts([segment], [post("TP-1", 9000.0)]) == ["AL-2-004"]


def test_a_post_on_the_boundary_counts_as_on_the_segment(segment: Segment) -> None:
    assert segments_without_posts([segment], [post("TP-1", 1200.0)]) == []


def test_the_report_carries_the_share_of_line_that_is_covered(
    line: Line, segment: Segment
) -> None:
    report = coverage(line, [segment], [post("TP-1", 1600.0)], reach_m=1600.0)
    assert report.posts == 1
    assert report.covered_m == pytest.approx(3200.0)
    assert report.covered_share == pytest.approx(3200.0 / line.length_m)
    assert report.uncovered_m == pytest.approx(line.length_m - 3200.0)


def test_a_line_with_no_posts_is_covered_nowhere(line: Line, segment: Segment) -> None:
    report = coverage(line, [segment], [])
    assert report.covered_share == pytest.approx(0.0)
    assert report.segments_without_posts == ("AL-2-004",)


def test_the_longest_gap_is_the_worst_blind_stretch(line: Line) -> None:
    posts = [post("TP-1", 1600.0), post("TP-2", 6000.0)]
    report = coverage(line, [], posts, reach_m=400.0)
    longest = report.longest_gap
    assert longest is not None
    assert longest.length_m == pytest.approx(line.length_m - 6400.0)


def test_a_fully_covered_line_has_no_longest_gap(line: Line) -> None:
    short = dataclasses.replace(line, length_m=1000.0)
    report = coverage(short, [], [post("TP-1", 500.0)], reach_m=600.0)
    assert report.gaps == ()
    assert report.longest_gap is None
    assert report.covered_share == pytest.approx(1.0)


def test_the_mean_spacing_needs_two_posts(line: Line) -> None:
    assert coverage(line, [], []).mean_spacing_m is None
    assert coverage(line, [], [post("TP-1", 0.0)]).mean_spacing_m is None
    two = coverage(line, [], [post("TP-1", 0.0), post("TP-2", 100.0)])
    assert two.mean_spacing_m == pytest.approx(line.length_m)


def test_a_shielding_coating_collapses_the_reach_of_a_post(
    segment: Segment,
) -> None:
    assert shielded_reach(segment) == pytest.approx(1600.0)
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    assert shielded_reach(taped) == pytest.approx(0.0)


def test_a_gap_knows_the_stretch_of_line_it_covers(line: Line) -> None:
    gaps = find_gaps(line, [post("TP-1", 1600.0)], reach_m=1600.0)
    assert gaps[0].extent == StationRange(Station(3200.0), Station(line.length_m))
