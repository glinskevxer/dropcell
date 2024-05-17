from __future__ import annotations

import dataclasses

import pytest

from dropcell.criteria.base import Evidence, Outcome
from dropcell.criteria.decay import (
    MINIMUM_DECAY_MV,
    PolarisationDecayCriterion,
    PolarisationFormationCriterion,
)
from dropcell.model.enums import ProtectionMethod
from dropcell.model.segment import Segment


def evidence(segment: Segment, **overrides: object) -> Evidence:
    return Evidence(segment=segment, **overrides)  # type: ignore[arg-type]


def test_a_hundred_millivolts_of_drift_meets_the_criterion(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-805.0)
    )
    assert result.outcome is Outcome.MET
    assert result.detail["decay_mv"] == pytest.approx(100.0)
    assert result.margin_mv == pytest.approx(0.0)


def test_more_drift_than_needed_still_meets_it(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-620.0)
    )
    assert result.outcome is Outcome.MET
    assert result.margin_mv == pytest.approx(185.0)


def test_too_little_drift_fails(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-838.0)
    )
    assert result.outcome is Outcome.NOT_MET
    assert result.note == "not enough decay"


def test_a_reading_taken_too_soon_is_not_decay(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-620.0, depolarised_after_hours=0.5)
    )
    assert result.outcome is Outcome.NOT_ASSESSED
    assert result.detail["hours"] == pytest.approx(0.5)


def test_a_reading_at_the_minimum_period_counts(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-620.0, depolarised_after_hours=2.0)
    )
    assert result.outcome is Outcome.MET


def test_an_unrecorded_period_is_taken_on_trust(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-620.0)
    )
    assert result.outcome is Outcome.MET


def test_decay_says_nothing_where_a_second_metal_is_bonded_on(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-620.0, dissimilar_metals=True)
    )
    assert result.outcome is Outcome.NOT_ASSESSED
    assert result.detail["dissimilar_metals"] is True


def test_decay_says_nothing_where_stray_current_is_suspected(segment: Segment) -> None:
    result = PolarisationDecayCriterion().assess(
        evidence(segment, off_mv=-905.0, depolarised_mv=-620.0, stray_current_suspected=True)
    )
    assert result.outcome is Outcome.NOT_ASSESSED


def test_missing_either_potential_leaves_it_unassessed(segment: Segment) -> None:
    criterion = PolarisationDecayCriterion()
    assert criterion.assess(evidence(segment, off_mv=-905.0)).detail["missing"] == [
        "depolarised_mv"
    ]
    assert criterion.assess(evidence(segment, depolarised_mv=-805.0)).detail["missing"] == [
        "off_mv"
    ]


def test_the_criterion_does_not_apply_to_unprotected_pipe(segment: Segment) -> None:
    bare = dataclasses.replace(segment, protection=ProtectionMethod.UNPROTECTED)
    assert not PolarisationDecayCriterion().applies_to(evidence(bare))


def test_the_criterion_does_not_apply_where_it_cannot_be_trusted(
    segment: Segment,
) -> None:
    criterion = PolarisationDecayCriterion()
    assert criterion.applies_to(evidence(segment))
    assert not criterion.applies_to(evidence(segment, dissimilar_metals=True))
    assert not criterion.applies_to(evidence(segment, stray_current_suspected=True))


def test_the_threshold_can_be_moved(segment: Segment) -> None:
    strict = PolarisationDecayCriterion(minimum_decay_mv=150.0)
    result = strict.assess(evidence(segment, off_mv=-905.0, depolarised_mv=-785.0))
    assert result.outcome is Outcome.NOT_MET
    assert result.detail["minimum_decay_mv"] == pytest.approx(150.0)


def test_formation_measures_the_shift_from_the_native_potential(
    segment: Segment,
) -> None:
    result = PolarisationFormationCriterion().assess(
        evidence(segment, native_mv=-580.0, off_mv=-905.0)
    )
    assert result.outcome is Outcome.MET
    assert result.detail["shift_mv"] == pytest.approx(325.0)


def test_formation_fails_when_the_pipe_barely_moved(segment: Segment) -> None:
    result = PolarisationFormationCriterion().assess(
        evidence(segment, native_mv=-580.0, off_mv=-640.0)
    )
    assert result.outcome is Outcome.NOT_MET
    assert result.margin_mv == pytest.approx(60.0 - MINIMUM_DECAY_MV)


def test_formation_needs_a_native_potential_to_apply(segment: Segment) -> None:
    criterion = PolarisationFormationCriterion()
    assert not criterion.applies_to(evidence(segment, off_mv=-905.0))
    assert criterion.applies_to(evidence(segment, native_mv=-580.0, off_mv=-905.0))
    assert criterion.assess(evidence(segment, off_mv=-905.0)).outcome is Outcome.NOT_ASSESSED
