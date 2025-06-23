from __future__ import annotations

import dataclasses

import pytest

from dropcell.analysis.coating import (
    BARE_DENSITY_MA_PER_M2,
    assess_coating,
    share_out,
    worst_first,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import CoatingType
from dropcell.model.segment import Segment


def test_a_segment_drawing_its_design_current_is_as_laid(segment: Segment) -> None:
    condition = assess_coating(segment, segment.design_current_ma)
    assert condition.breakdown_factor == pytest.approx(1.0)
    assert condition.verdict == "as laid"
    assert not condition.is_worth_investigating


def test_a_segment_drawing_ten_times_is_sound_with_defects(segment: Segment) -> None:
    condition = assess_coating(segment, segment.design_current_ma * 10)
    assert condition.verdict == "sound with defects"
    assert not condition.is_worth_investigating


def test_a_segment_drawing_fifty_times_is_degraded(segment: Segment) -> None:
    condition = assess_coating(segment, segment.design_current_ma * 50)
    assert condition.verdict == "degraded"
    assert condition.is_worth_investigating


def test_a_segment_drawing_hundreds_of_times_has_failed(segment: Segment) -> None:
    condition = assess_coating(segment, segment.design_current_ma * 400)
    assert condition.verdict == "failed"


def test_the_bands_are_closed_at_the_top(segment: Segment) -> None:
    assert assess_coating(segment, segment.design_current_ma * 5).verdict == "as laid"
    assert (
        assess_coating(segment, segment.design_current_ma * 25).verdict == "sound with defects"
    )
    assert assess_coating(segment, segment.design_current_ma * 100).verdict == "degraded"


def test_the_excess_is_never_negative(segment: Segment) -> None:
    condition = assess_coating(segment, segment.design_current_ma / 2)
    assert condition.excess_current_ma == pytest.approx(0.0)
    assert condition.implied_bare_area_m2 == pytest.approx(0.0)


def test_the_implied_bare_area_divides_the_excess_by_the_bare_density(
    segment: Segment,
) -> None:
    condition = assess_coating(segment, segment.design_current_ma + 215.0)
    assert condition.implied_bare_area_m2 == pytest.approx(215.0 / BARE_DENSITY_MA_PER_M2)


def test_the_implied_share_is_over_the_segment_area(segment: Segment) -> None:
    condition = assess_coating(segment, segment.design_current_ma + 215.0)
    assert condition.implied_bare_share == pytest.approx(
        condition.implied_bare_area_m2 / segment.external_area_m2
    )


def test_a_negative_current_is_refused(segment: Segment) -> None:
    with pytest.raises(ValidationError):
        assess_coating(segment, -1.0)


def test_the_explanation_names_both_numbers(segment: Segment) -> None:
    text = assess_coating(segment, segment.design_current_ma * 10).explain()
    assert "AL-2-004" in text
    assert "coal_tar as laid" in text
    assert "a factor of 10" in text


def test_a_bare_segment_drawing_its_design_current_is_as_laid(
    segment: Segment,
) -> None:
    bare = dataclasses.replace(segment, coating=CoatingType.BARE)
    condition = assess_coating(bare, bare.design_current_ma)
    assert condition.verdict == "as laid"


def test_a_rectifier_output_is_split_by_design_current(segment: Segment) -> None:
    coated = segment
    bare = dataclasses.replace(segment, code="AL-2-005", coating=CoatingType.BARE)
    split = share_out([coated, bare], 1000.0)
    assert sum(split.values()) == pytest.approx(1000.0)
    assert split["AL-2-005"] > split["AL-2-004"] * 100


def test_two_identical_segments_split_the_output_evenly(segment: Segment) -> None:
    twin = dataclasses.replace(segment, code="AL-2-005")
    split = share_out([segment, twin], 100.0)
    assert split["AL-2-004"] == pytest.approx(50.0)
    assert split["AL-2-005"] == pytest.approx(50.0)


def test_a_negative_output_is_refused(segment: Segment) -> None:
    with pytest.raises(ValidationError):
        share_out([segment], -1.0)


def test_splitting_across_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        share_out([], 100.0)


def test_ordering_puts_the_worst_draw_first(segment: Segment) -> None:
    mild = assess_coating(segment, segment.design_current_ma * 2)
    bad = assess_coating(
        dataclasses.replace(segment, code="AL-2-005"), segment.design_current_ma * 200
    )
    assert [item.segment_code for item in worst_first([mild, bad])] == [
        "AL-2-005",
        "AL-2-004",
    ]
