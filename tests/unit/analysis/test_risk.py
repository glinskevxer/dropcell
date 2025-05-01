from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.risk import (
    MAX_AGE_TERM,
    MAX_STALENESS,
    age_term,
    by_exposure,
    rank,
    score_segment,
    staleness_term,
    total_exposure,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import ClassLocation, CoatingType, ProtectionMethod
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange

TODAY = dt.date(2025, 3, 14)


def test_new_pipe_carries_no_age_term() -> None:
    assert age_term(0) == pytest.approx(1.0)


def test_old_pipe_carries_more() -> None:
    assert age_term(50) == pytest.approx(1.6)
    assert age_term(1000) == pytest.approx(MAX_AGE_TERM)


def test_a_negative_age_is_refused() -> None:
    with pytest.raises(ValidationError):
        age_term(-1)


def test_a_freshly_surveyed_segment_carries_no_staleness() -> None:
    assert staleness_term(0.0) == pytest.approx(1.0)


def test_staleness_grows_and_is_capped() -> None:
    assert staleness_term(4.0) == pytest.approx(2.0)
    assert staleness_term(100.0) == pytest.approx(MAX_STALENESS)


def test_never_surveyed_is_treated_as_ten_years() -> None:
    assert staleness_term(None) == staleness_term(10.0)


def test_a_survey_in_the_future_is_refused() -> None:
    with pytest.raises(ValidationError):
        staleness_term(-1.0)


def test_an_old_segment_scores_above_a_new_one(segment: Segment) -> None:
    old = score_segment(segment, as_of=TODAY)
    new = score_segment(dataclasses.replace(segment, installed_year=2020), as_of=TODAY)
    assert old.score > new.score


def test_a_stale_segment_scores_above_a_freshly_walked_one(segment: Segment) -> None:
    stale = score_segment(segment, as_of=TODAY, years_since_survey=8.0)
    fresh = score_segment(segment, as_of=TODAY, years_since_survey=0.0)
    assert stale.score > fresh.score


def test_corrosive_soil_raises_the_score(segment: Segment) -> None:
    wet = score_segment(dataclasses.replace(segment, soil_resistivity_ohm_m=6.0), as_of=TODAY)
    dry = score_segment(dataclasses.replace(segment, soil_resistivity_ohm_m=200.0), as_of=TODAY)
    assert wet.score > dry.score


def test_unmeasured_soil_sits_between_the_extremes(segment: Segment) -> None:
    unknown = score_segment(segment, as_of=TODAY).score
    dry = score_segment(
        dataclasses.replace(segment, soil_resistivity_ohm_m=200.0), as_of=TODAY
    ).score
    wet = score_segment(
        dataclasses.replace(segment, soil_resistivity_ohm_m=6.0), as_of=TODAY
    ).score
    assert dry < unknown < wet


def test_a_shielding_coating_adds_a_term(segment: Segment) -> None:
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    scored = score_segment(taped, as_of=TODAY)
    assert any(name == "coating can shield" for name, _ in scored.terms)


def test_unprotected_pipe_adds_the_biggest_single_term(segment: Segment) -> None:
    bare = dataclasses.replace(segment, protection=ProtectionMethod.UNPROTECTED)
    scored = score_segment(bare, as_of=TODAY)
    assert any(name == "no protection on it" for name, _ in scored.terms)
    assert scored.score > score_segment(segment, as_of=TODAY).score * 2


def test_a_built_up_class_location_raises_the_score(segment: Segment) -> None:
    urban = dataclasses.replace(segment, class_location=ClassLocation.URBAN)
    assert score_segment(urban, as_of=TODAY).score > score_segment(segment, as_of=TODAY).score


def test_pipe_out_of_reach_of_a_post_adds_a_term(segment: Segment) -> None:
    blind = score_segment(segment, as_of=TODAY, covered_share=0.0)
    covered = score_segment(segment, as_of=TODAY, covered_share=1.0)
    assert blind.score > covered.score
    assert any("out of reach" in name for name, _ in blind.terms)


def test_a_fully_covered_segment_carries_no_reach_term(segment: Segment) -> None:
    scored = score_segment(segment, as_of=TODAY, covered_share=1.0)
    assert not any("out of reach" in name for name, _ in scored.terms)


def test_a_coverage_share_outside_nought_to_one_is_refused(segment: Segment) -> None:
    with pytest.raises(ValidationError):
        score_segment(segment, as_of=TODAY, covered_share=1.4)


def test_the_score_is_the_product_of_its_terms(segment: Segment) -> None:
    scored = score_segment(segment, as_of=TODAY, covered_share=0.5)
    product = 1.0
    for _, weight in scored.terms:
        product *= weight
    assert scored.score == pytest.approx(product)


def test_the_explanation_writes_the_multiplication_out(segment: Segment) -> None:
    text = score_segment(segment, as_of=TODAY).explain()
    assert text.startswith("AL-2-004:")
    assert " x " in text


def test_exposure_weights_the_score_by_length(segment: Segment) -> None:
    scored = score_segment(segment, as_of=TODAY)
    assert scored.exposure == pytest.approx(scored.score * 1.2)


def test_a_long_mild_segment_can_outweigh_a_short_bad_one(segment: Segment) -> None:
    short_bad = score_segment(
        dataclasses.replace(
            segment,
            code="AL-2-005",
            extent=StationRange(Station(0.0), Station(50.0)),
            protection=ProtectionMethod.UNPROTECTED,
        ),
        as_of=TODAY,
    )
    long_mild = score_segment(
        dataclasses.replace(
            segment, code="AL-2-006", extent=StationRange(Station(0.0), Station(9000.0))
        ),
        as_of=TODAY,
    )
    assert short_bad.score > long_mild.score
    assert [item.segment_code for item in by_exposure([short_bad, long_mild])] == [
        "AL-2-006",
        "AL-2-005",
    ]


def test_ranking_puts_the_worst_score_first(segment: Segment) -> None:
    mild = score_segment(segment, as_of=TODAY)
    bad = score_segment(
        dataclasses.replace(segment, code="AL-2-005", protection=ProtectionMethod.UNPROTECTED),
        as_of=TODAY,
    )
    assert [item.segment_code for item in rank([mild, bad])] == ["AL-2-005", "AL-2-004"]


def test_the_total_exposure_adds_the_segments_up(segment: Segment) -> None:
    first = score_segment(segment, as_of=TODAY)
    second = score_segment(dataclasses.replace(segment, code="AL-2-005"), as_of=TODAY)
    assert total_exposure([first, second]) == pytest.approx(first.exposure * 2)
