from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.priority import (
    DigBand,
    age_of,
    band_for,
    dig_list,
    in_band,
    rank,
    score_defect,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import ClassLocation, CoatingType, Commodity
from dropcell.model.segment import Segment
from dropcell.survey.dcvg import DcvgCategory


def test_a_worse_category_scores_higher(segment: Segment) -> None:
    small = score_defect("a", category=DcvgCategory.ONE, segment=segment)
    large = score_defect("b", category=DcvgCategory.FOUR, segment=segment)
    assert large.score > small.score


def test_corrosive_soil_multiplies_the_score(segment: Segment) -> None:
    dry = dataclasses.replace(segment, soil_resistivity_ohm_m=200.0)
    wet = dataclasses.replace(segment, soil_resistivity_ohm_m=6.0)
    assert (
        score_defect("b", category=DcvgCategory.TWO, segment=wet).score
        > score_defect("a", category=DcvgCategory.TWO, segment=dry).score
    )


def test_unmeasured_soil_sits_between_the_extremes(segment: Segment) -> None:
    unknown = score_defect("a", category=DcvgCategory.TWO, segment=segment).score
    benign = score_defect(
        "b",
        category=DcvgCategory.TWO,
        segment=dataclasses.replace(segment, soil_resistivity_ohm_m=200.0),
    ).score
    worst = score_defect(
        "c",
        category=DcvgCategory.TWO,
        segment=dataclasses.replace(segment, soil_resistivity_ohm_m=6.0),
    ).score
    assert benign < unknown < worst


def test_a_built_up_class_location_raises_the_score(segment: Segment) -> None:
    urban = dataclasses.replace(segment, class_location=ClassLocation.URBAN)
    assert (
        score_defect("b", category=DcvgCategory.TWO, segment=urban).score
        > score_defect("a", category=DcvgCategory.TWO, segment=segment).score
    )


def test_a_shielding_coating_adds_a_term(segment: Segment) -> None:
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    scored = score_defect("a", category=DcvgCategory.TWO, segment=taped)
    assert any(name == "shielding coating" for name, _ in scored.terms)


def test_shallow_cover_adds_a_term(segment: Segment) -> None:
    shallow = dataclasses.replace(segment, depth_of_cover_m=0.6)
    scored = score_defect("a", category=DcvgCategory.TWO, segment=shallow)
    assert any(name == "shallow cover" for name, _ in scored.terms)


def test_an_anodic_defect_doubles(segment: Segment) -> None:
    plain = score_defect("a", category=DcvgCategory.TWO, segment=segment)
    anodic = score_defect("b", category=DcvgCategory.TWO, segment=segment, anodic=True)
    assert anodic.score == pytest.approx(plain.score * 2.0)


def test_a_liquid_line_scores_above_a_gas_line(segment: Segment) -> None:
    gas = score_defect("a", category=DcvgCategory.TWO, segment=segment)
    oil = score_defect(
        "b", category=DcvgCategory.TWO, segment=segment, commodity=Commodity.CRUDE_OIL
    )
    assert oil.score > gas.score


def test_old_pipe_adds_a_term_and_new_pipe_does_not(segment: Segment) -> None:
    old = score_defect("a", category=DcvgCategory.TWO, segment=segment, age_years=60)
    new = score_defect("b", category=DcvgCategory.TWO, segment=segment, age_years=10)
    assert any("fifty years" in name for name, _ in old.terms)
    assert not any("fifty years" in name for name, _ in new.terms)


def test_the_score_is_the_product_of_its_terms(segment: Segment) -> None:
    scored = score_defect("a", category=DcvgCategory.THREE, segment=segment)
    product = 1.0
    for _, weight in scored.terms:
        product *= weight
    assert scored.score == pytest.approx(product)


def test_one_high_term_cannot_carry_a_trivial_finding(segment: Segment) -> None:
    urban_trivial = score_defect(
        "a",
        category=DcvgCategory.ONE,
        segment=dataclasses.replace(segment, class_location=ClassLocation.URBAN),
    )
    rural_severe = score_defect("b", category=DcvgCategory.FOUR, segment=segment)
    assert rural_severe.score > urban_trivial.score


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0.0, DigBand.ROUTINE),
        (1.99, DigBand.ROUTINE),
        (2.0, DigBand.PLANNED),
        (3.99, DigBand.PLANNED),
        (4.0, DigBand.PRIORITY),
        (7.99, DigBand.PRIORITY),
        (8.0, DigBand.IMMEDIATE),
        (99.0, DigBand.IMMEDIATE),
    ],
)
def test_the_bands_are_closed_at_the_bottom(score: float, band: DigBand) -> None:
    assert band_for(score) is band


def test_a_negative_score_has_no_band() -> None:
    with pytest.raises(ValidationError):
        band_for(-1.0)


def test_the_bands_sort_in_the_order_work_happens() -> None:
    ranks = [
        band.rank
        for band in (DigBand.ROUTINE, DigBand.PLANNED, DigBand.PRIORITY, DigBand.IMMEDIATE)
    ]
    assert ranks == sorted(ranks)


def test_the_explanation_writes_the_multiplication_out(segment: Segment) -> None:
    text = score_defect("XG-4", category=DcvgCategory.THREE, segment=segment).explain()
    assert text.startswith("XG-4:")
    assert " x " in text
    assert "category 2.60" in text


def test_ranking_puts_the_worst_first(segment: Segment) -> None:
    small = score_defect("a", category=DcvgCategory.ONE, segment=segment)
    large = score_defect("b", category=DcvgCategory.FOUR, segment=segment)
    assert [item.reference for item in rank([small, large])] == ["b", "a"]


def test_ties_are_broken_on_the_reference(segment: Segment) -> None:
    first = score_defect("a", category=DcvgCategory.TWO, segment=segment)
    second = score_defect("b", category=DcvgCategory.TWO, segment=segment)
    assert [item.reference for item in rank([second, first])] == ["a", "b"]


def test_a_band_can_be_pulled_out_on_its_own(segment: Segment) -> None:
    small = score_defect("a", category=DcvgCategory.ONE, segment=segment)
    large = score_defect("b", category=DcvgCategory.FOUR, segment=segment)
    assert in_band([small, large], small.band) == [small]


def test_a_budget_takes_the_worst_n(segment: Segment) -> None:
    scores = [
        score_defect("a", category=DcvgCategory.ONE, segment=segment),
        score_defect("b", category=DcvgCategory.FOUR, segment=segment),
        score_defect("c", category=DcvgCategory.THREE, segment=segment),
    ]
    assert [item.reference for item in dig_list(scores, 2)] == ["b", "c"]
    assert dig_list(scores, 0) == []


def test_a_negative_budget_is_refused(segment: Segment) -> None:
    with pytest.raises(ValidationError):
        dig_list([], -1)


def test_the_age_helper_counts_years_since_it_went_in(segment: Segment) -> None:
    assert age_of(segment, dt.date(2025, 3, 14)) == 51
