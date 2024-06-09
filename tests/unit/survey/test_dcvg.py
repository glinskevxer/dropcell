from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.stationing import Station
from dropcell.survey.dcvg import (
    DcvgCategory,
    DcvgIndication,
    anodic_indications,
    classify_percent_ir,
    rank_indications,
)


def indication(**overrides: object) -> DcvgIndication:
    kwargs: dict[str, object] = {
        "line_code": "AL-2",
        "station": Station(1245.5),
        "gradient_mv": 40.0,
        "section_shift_mv": 400.0,
        "found_on": dt.date(2025, 3, 14),
    }
    kwargs.update(overrides)
    return DcvgIndication(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("percent", "category"),
    [
        (0.0, DcvgCategory.ONE),
        (15.9, DcvgCategory.ONE),
        (16.0, DcvgCategory.TWO),
        (35.9, DcvgCategory.TWO),
        (36.0, DcvgCategory.THREE),
        (70.9, DcvgCategory.THREE),
        (71.0, DcvgCategory.FOUR),
        (100.0, DcvgCategory.FOUR),
    ],
)
def test_the_bands_are_closed_at_the_bottom(percent: float, category: DcvgCategory) -> None:
    assert classify_percent_ir(percent) is category


@pytest.mark.parametrize("percent", [-1.0, 100.1])
def test_a_share_outside_nought_to_a_hundred_is_refused(percent: float) -> None:
    with pytest.raises(ValidationError):
        classify_percent_ir(percent)


def test_the_percent_ir_is_the_gradient_over_the_section_shift() -> None:
    assert indication().percent_ir == pytest.approx(10.0)
    assert indication(gradient_mv=300.0).percent_ir == pytest.approx(75.0)


def test_the_same_defect_in_different_soil_gives_the_same_share() -> None:
    wet = indication(gradient_mv=20.0, section_shift_mv=200.0)
    dry = indication(gradient_mv=200.0, section_shift_mv=2000.0)
    assert wet.percent_ir == pytest.approx(dry.percent_ir)
    assert wet.category is dry.category


def test_a_negative_gradient_is_refused() -> None:
    with pytest.raises(ValidationError):
        indication(gradient_mv=-4.0)


def test_a_section_shift_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        indication(section_shift_mv=0.0)


def test_a_gradient_bigger_than_the_section_shift_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        indication(gradient_mv=500.0, section_shift_mv=400.0)
    assert caught.value.detail["section_shift_mv"] == pytest.approx(400.0)


def test_the_line_code_is_normalised() -> None:
    assert indication(line_code="al 2").line_code == "AL-2"


def test_a_severe_indication_is_dealt_with_soonest() -> None:
    severe = indication(gradient_mv=380.0)
    assert severe.category is DcvgCategory.FOUR
    assert severe.category.is_immediate
    assert severe.due_by == dt.date(2025, 4, 13)


def test_a_minor_indication_has_no_date_at_all() -> None:
    minor = indication(gradient_mv=20.0)
    assert minor.category is DcvgCategory.ONE
    assert minor.category.response_days is None
    assert minor.due_by is None


def test_the_middle_bands_carry_their_own_response_times() -> None:
    assert indication(gradient_mv=100.0).due_by == dt.date(2026, 3, 14)
    assert indication(gradient_mv=200.0).due_by == dt.date(2025, 9, 10)


def test_only_the_top_band_is_dug_without_waiting() -> None:
    assert DcvgCategory.FOUR.is_immediate
    assert not DcvgCategory.THREE.is_immediate


def test_every_category_carries_a_label() -> None:
    for category in DcvgCategory:
        assert category.label


def test_ranking_puts_the_worst_share_first() -> None:
    small = indication(gradient_mv=20.0)
    large = indication(gradient_mv=300.0, station=Station(900.0))
    assert rank_indications([small, large]) == [large, small]


def test_ranking_breaks_a_tie_on_where_the_defect_is() -> None:
    far = indication(station=Station(4000.0))
    near = indication(station=Station(100.0))
    assert rank_indications([far, near]) == [near, far]


def test_anodic_indications_are_pulled_out_on_their_own() -> None:
    cathodic = indication(gradient_mv=300.0)
    anodic = indication(gradient_mv=20.0, anodic=True, station=Station(800.0))
    assert anodic_indications([cathodic, anodic]) == [anodic]


def test_a_survey_with_no_anodic_indications_gives_an_empty_list() -> None:
    assert anodic_indications([indication()]) == []
