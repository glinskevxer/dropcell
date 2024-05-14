from __future__ import annotations

import dataclasses

import pytest

from dropcell.criteria.base import Evidence, Outcome
from dropcell.criteria.potential import (
    ANAEROBIC_PROTECTION_MV,
    DEFAULT_PROTECTION_MV,
    OnPotentialCriterion,
    PolarisedPotentialCriterion,
    anaerobic_polarised_criterion,
)
from dropcell.model.enums import ProtectionMethod
from dropcell.model.segment import Segment


def evidence(segment: Segment, **overrides: object) -> Evidence:
    return Evidence(segment=segment, **overrides)  # type: ignore[arg-type]


def test_a_potential_past_the_threshold_meets_the_criterion(segment: Segment) -> None:
    result = PolarisedPotentialCriterion().assess(evidence(segment, off_mv=-905.0))
    assert result.outcome is Outcome.MET
    assert result.margin_mv == pytest.approx(55.0)


def test_a_potential_exactly_on_the_threshold_meets_it(segment: Segment) -> None:
    result = PolarisedPotentialCriterion().assess(evidence(segment, off_mv=-850.0))
    assert result.outcome is Outcome.MET
    assert result.margin_mv == pytest.approx(0.0)


def test_a_potential_short_of_the_threshold_does_not(segment: Segment) -> None:
    result = PolarisedPotentialCriterion().assess(evidence(segment, off_mv=-812.0))
    assert result.outcome is Outcome.NOT_MET
    assert result.margin_mv == pytest.approx(-38.0)
    assert "short" in result.note


def test_the_detail_carries_both_numbers_that_were_compared(segment: Segment) -> None:
    result = PolarisedPotentialCriterion().assess(evidence(segment, off_mv=-812.0))
    assert result.detail == {"off_mv": -812.0, "threshold_mv": DEFAULT_PROTECTION_MV}


def test_without_an_off_potential_nothing_is_assessed(segment: Segment) -> None:
    result = PolarisedPotentialCriterion().assess(evidence(segment, on_mv=-1120.0))
    assert result.outcome is Outcome.NOT_ASSESSED
    assert result.detail["missing"] == ["off_mv"]


def test_the_polarised_criterion_applies_to_anything_with_current_on_it(
    segment: Segment,
) -> None:
    criterion = PolarisedPotentialCriterion()
    assert criterion.applies_to(evidence(segment))
    galvanic = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    assert criterion.applies_to(evidence(galvanic))
    bare = dataclasses.replace(segment, protection=ProtectionMethod.UNPROTECTED)
    assert not criterion.applies_to(evidence(bare))


def test_the_anaerobic_threshold_is_a_hundred_millivolts_tighter(segment: Segment) -> None:
    ordinary = PolarisedPotentialCriterion()
    tight = anaerobic_polarised_criterion()
    assert tight.threshold_mv == pytest.approx(ANAEROBIC_PROTECTION_MV)
    reading = evidence(segment, off_mv=-905.0)
    assert ordinary.assess(reading).outcome is Outcome.MET
    assert tight.assess(reading).outcome is Outcome.NOT_MET


def test_the_on_potential_criterion_is_refused_where_interruption_is_possible(
    segment: Segment,
) -> None:
    result = OnPotentialCriterion().assess(evidence(segment, on_mv=-1120.0))
    assert result.outcome is Outcome.NOT_ASSESSED
    assert "interrupted" in result.note


def test_the_on_potential_criterion_works_on_a_galvanic_segment(segment: Segment) -> None:
    galvanic = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    result = OnPotentialCriterion().assess(evidence(galvanic, on_mv=-905.0))
    assert result.outcome is Outcome.MET
    assert result.note == "includes IR drop"


def test_a_galvanic_segment_short_of_the_threshold_fails(segment: Segment) -> None:
    galvanic = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    result = OnPotentialCriterion().assess(evidence(galvanic, on_mv=-780.0))
    assert result.outcome is Outcome.NOT_MET
    assert result.margin_mv == pytest.approx(-70.0)


def test_a_galvanic_segment_with_no_on_potential_is_not_assessed(segment: Segment) -> None:
    galvanic = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    result = OnPotentialCriterion().assess(evidence(galvanic))
    assert result.detail["missing"] == ["on_mv"]


def test_the_on_potential_criterion_only_applies_to_galvanic_segments(
    segment: Segment,
) -> None:
    criterion = OnPotentialCriterion()
    galvanic = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    assert criterion.applies_to(evidence(galvanic))
    assert not criterion.applies_to(evidence(segment))


def test_both_criteria_answer_to_the_protocol() -> None:
    from dropcell.criteria.base import Criterion

    assert isinstance(PolarisedPotentialCriterion(), Criterion)
    assert isinstance(OnPotentialCriterion(), Criterion)
