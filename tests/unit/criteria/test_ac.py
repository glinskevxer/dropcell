from __future__ import annotations

import dataclasses
import math

import pytest

from dropcell.criteria.ac import (
    AC_DENSITY_HIGH_RISK,
    AC_DENSITY_LOW_RISK,
    STANDARD_COUPON_AREA_M2,
    AcCorrosionLimit,
    AcToDcRatioLimit,
    TouchVoltageLimit,
    ac_current_density,
    equivalent_diameter_m,
)
from dropcell.criteria.base import Evidence, Outcome
from dropcell.errors import ValidationError
from dropcell.model.segment import Segment


def evidence(segment: Segment, **overrides: object) -> Evidence:
    return Evidence(segment=segment, **overrides)  # type: ignore[arg-type]


def test_a_square_centimetre_coupon_is_about_eleven_millimetres_across() -> None:
    assert equivalent_diameter_m(STANDARD_COUPON_AREA_M2) == pytest.approx(0.011284, abs=1e-6)


def test_the_equivalent_diameter_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        equivalent_diameter_m(0.0)


def test_density_falls_as_the_soil_gets_more_resistive() -> None:
    wet = ac_current_density(4.0, 10.0)
    dry = ac_current_density(4.0, 100.0)
    assert wet == pytest.approx(dry * 10.0)


def test_density_rises_with_the_voltage_on_the_pipe() -> None:
    assert ac_current_density(8.0, 25.0) == pytest.approx(ac_current_density(4.0, 25.0) * 2)


def test_the_density_formula_matches_the_hand_calculation() -> None:
    diameter = equivalent_diameter_m(STANDARD_COUPON_AREA_M2)
    assert ac_current_density(4.0, 25.0) == pytest.approx(
        8.0 * 4.0 / (25.0 * math.pi * diameter)
    )


@pytest.mark.parametrize(("volts", "resistivity"), [(-1.0, 25.0), (4.0, 0.0)])
def test_impossible_inputs_are_refused(volts: float, resistivity: float) -> None:
    with pytest.raises(ValidationError):
        ac_current_density(volts, resistivity)


def test_a_low_density_meets_the_limit(segment: Segment) -> None:
    result = AcCorrosionLimit().assess(evidence(segment, ac_current_density_a_per_m2=12.0))
    assert result.outcome is Outcome.MET


def test_the_middle_band_is_a_finding_but_not_an_exceedance(segment: Segment) -> None:
    result = AcCorrosionLimit().assess(
        evidence(segment, ac_current_density_a_per_m2=AC_DENSITY_LOW_RISK)
    )
    assert result.outcome is Outcome.NOT_MET
    assert "mitigation" in result.note


def test_the_top_band_is_an_exceedance(segment: Segment) -> None:
    result = AcCorrosionLimit().assess(
        evidence(segment, ac_current_density_a_per_m2=AC_DENSITY_HIGH_RISK)
    )
    assert result.outcome is Outcome.EXCEEDED


def test_a_density_can_be_worked_out_from_voltage_and_soil(segment: Segment) -> None:
    wet = dataclasses.replace(segment, soil_resistivity_ohm_m=8.0)
    result = AcCorrosionLimit().assess(evidence(wet, ac_voltage_v=4.0))
    assert result.outcome is Outcome.EXCEEDED
    assert result.detail["ac_current_density_a_per_m2"] == pytest.approx(
        ac_current_density(4.0, 8.0)
    )


def test_the_evidence_resistivity_beats_the_segment_one(segment: Segment) -> None:
    wet = dataclasses.replace(segment, soil_resistivity_ohm_m=8.0)
    result = AcCorrosionLimit().assess(
        evidence(wet, ac_voltage_v=4.0, soil_resistivity_ohm_m=200.0)
    )
    assert result.detail["ac_current_density_a_per_m2"] == pytest.approx(
        ac_current_density(4.0, 200.0)
    )


def test_a_voltage_with_no_resistivity_anywhere_cannot_be_turned_into_a_density(
    segment: Segment,
) -> None:
    limit = AcCorrosionLimit()
    reading = evidence(segment, ac_voltage_v=4.0)
    assert not limit.applies_to(reading)
    assert limit.assess(reading).outcome is Outcome.NOT_ASSESSED


def test_the_ratio_limit_ignores_a_small_dc_side(segment: Segment) -> None:
    limit = AcToDcRatioLimit()
    reading = evidence(
        segment, ac_current_density_a_per_m2=40.0, dc_current_density_a_per_m2=0.2
    )
    assert not limit.applies_to(reading)
    assert limit.assess(reading).outcome is Outcome.NOT_ASSESSED


def test_a_high_ratio_over_a_real_dc_side_is_an_exceedance(segment: Segment) -> None:
    result = AcToDcRatioLimit().assess(
        evidence(segment, ac_current_density_a_per_m2=40.0, dc_current_density_a_per_m2=2.0)
    )
    assert result.outcome is Outcome.EXCEEDED
    assert result.detail["ratio"] == pytest.approx(20.0)


def test_a_ratio_inside_the_limit_passes(segment: Segment) -> None:
    result = AcToDcRatioLimit().assess(
        evidence(segment, ac_current_density_a_per_m2=6.0, dc_current_density_a_per_m2=2.0)
    )
    assert result.outcome is Outcome.MET


def test_the_ratio_limit_needs_both_densities(segment: Segment) -> None:
    result = AcToDcRatioLimit().assess(evidence(segment, ac_current_density_a_per_m2=40.0))
    assert result.detail["missing"] == ["dc_current_density_a_per_m2"]


def test_touch_voltage_is_a_safety_limit_not_a_corrosion_one(segment: Segment) -> None:
    limit = TouchVoltageLimit()
    assert limit.assess(evidence(segment, ac_voltage_v=15.0)).outcome is Outcome.MET
    hot = limit.assess(evidence(segment, ac_voltage_v=22.0))
    assert hot.outcome is Outcome.EXCEEDED
    assert hot.detail["ac_voltage_v"] == pytest.approx(22.0)


def test_touch_voltage_needs_a_voltage(segment: Segment) -> None:
    limit = TouchVoltageLimit()
    assert not limit.applies_to(evidence(segment))
    assert limit.assess(evidence(segment)).outcome is Outcome.NOT_ASSESSED
