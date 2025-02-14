from __future__ import annotations

import dataclasses

import pytest

from dropcell.criteria.base import Evidence, Outcome
from dropcell.criteria.shift import (
    HISTORIC_SHIFT_MV,
    NegativeShiftIndicator,
    shift_is_suspect,
)
from dropcell.model.enums import CoatingType, ProtectionMethod
from dropcell.model.segment import Segment


def evidence(segment: Segment, **overrides: object) -> Evidence:
    return Evidence(segment=segment, **overrides)  # type: ignore[arg-type]


def test_a_large_shift_is_reported_and_still_not_met(segment: Segment) -> None:
    result = NegativeShiftIndicator().assess(evidence(segment, native_mv=-580.0, off_mv=-905.0))
    assert result.outcome is Outcome.NOT_MET
    assert result.detail["shift_mv"] == pytest.approx(325.0)
    assert result.detail["reached"] is True
    assert "withdrawn" in result.note


def test_a_small_shift_says_it_did_not_even_reach_the_old_figure(
    segment: Segment,
) -> None:
    result = NegativeShiftIndicator().assess(evidence(segment, native_mv=-580.0, off_mv=-700.0))
    assert result.detail["reached"] is False
    assert "not even" in result.note


def test_the_shift_is_measured_against_the_off_potential_when_there_is_one(
    segment: Segment,
) -> None:
    result = NegativeShiftIndicator().assess(
        evidence(segment, native_mv=-580.0, on_mv=-1120.0, off_mv=-905.0)
    )
    assert result.detail["protected_mv"] == pytest.approx(-905.0)


def test_the_on_potential_is_used_when_there_is_no_off(segment: Segment) -> None:
    result = NegativeShiftIndicator().assess(evidence(segment, native_mv=-580.0, on_mv=-1120.0))
    assert result.detail["protected_mv"] == pytest.approx(-1120.0)
    assert result.detail["shift_mv"] == pytest.approx(540.0)


def test_it_never_returns_a_satisfied_outcome(segment: Segment) -> None:
    for off in (-905.0, -1400.0, -600.0):
        result = NegativeShiftIndicator().assess(
            evidence(segment, native_mv=-580.0, off_mv=off)
        )
        assert result.outcome is not Outcome.MET


def test_without_a_native_potential_nothing_is_assessed(segment: Segment) -> None:
    result = NegativeShiftIndicator().assess(evidence(segment, off_mv=-905.0))
    assert result.outcome is Outcome.NOT_ASSESSED
    assert result.detail["missing"] == ["native_mv"]


def test_without_any_protected_potential_nothing_is_assessed(
    segment: Segment,
) -> None:
    result = NegativeShiftIndicator().assess(evidence(segment, native_mv=-580.0))
    assert result.outcome is Outcome.NOT_ASSESSED


def test_it_does_not_apply_to_unprotected_pipe(segment: Segment) -> None:
    bare = dataclasses.replace(segment, protection=ProtectionMethod.UNPROTECTED)
    assert not NegativeShiftIndicator().applies_to(
        evidence(bare, native_mv=-580.0, off_mv=-905.0)
    )


def test_it_applies_wherever_there_is_a_native_potential(segment: Segment) -> None:
    criterion = NegativeShiftIndicator()
    assert criterion.applies_to(evidence(segment, native_mv=-580.0, off_mv=-905.0))
    assert not criterion.applies_to(evidence(segment, off_mv=-905.0))


def test_the_figure_can_be_moved(segment: Segment) -> None:
    strict = NegativeShiftIndicator(minimum_shift_mv=500.0)
    result = strict.assess(evidence(segment, native_mv=-580.0, off_mv=-905.0))
    assert result.detail["reached"] is False
    assert result.detail["minimum_shift_mv"] == pytest.approx(500.0)


def test_a_shift_on_bare_pipe_in_wet_ground_is_suspect(segment: Segment) -> None:
    bare_wet = dataclasses.replace(
        segment, coating=CoatingType.BARE, soil_resistivity_ohm_m=8.0
    )
    assert shift_is_suspect(evidence(bare_wet), HISTORIC_SHIFT_MV)


def test_the_same_shift_on_coated_pipe_is_not(segment: Segment) -> None:
    coated_wet = dataclasses.replace(segment, soil_resistivity_ohm_m=8.0)
    assert not shift_is_suspect(evidence(coated_wet), HISTORIC_SHIFT_MV)


def test_bare_pipe_in_dry_ground_is_not_suspect(segment: Segment) -> None:
    bare_dry = dataclasses.replace(
        segment, coating=CoatingType.BARE, soil_resistivity_ohm_m=200.0
    )
    assert not shift_is_suspect(evidence(bare_dry), HISTORIC_SHIFT_MV)


def test_a_small_shift_is_never_suspect(segment: Segment) -> None:
    bare_wet = dataclasses.replace(
        segment, coating=CoatingType.BARE, soil_resistivity_ohm_m=8.0
    )
    assert not shift_is_suspect(evidence(bare_wet), 100.0)


def test_bare_pipe_with_no_soil_measurement_cannot_be_called_suspect(
    segment: Segment,
) -> None:
    bare = dataclasses.replace(segment, coating=CoatingType.BARE)
    assert not shift_is_suspect(evidence(bare), HISTORIC_SHIFT_MV)


def test_the_evidence_resistivity_beats_the_segment_one(segment: Segment) -> None:
    bare_dry = dataclasses.replace(
        segment, coating=CoatingType.BARE, soil_resistivity_ohm_m=200.0
    )
    assert shift_is_suspect(evidence(bare_dry, soil_resistivity_ohm_m=8.0), HISTORIC_SHIFT_MV)
