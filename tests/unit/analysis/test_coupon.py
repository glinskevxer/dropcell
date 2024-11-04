from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.coupon import assess_coupon, build_evidence, worst_first
from dropcell.criteria.registry import IMPRESSED_CURRENT
from dropcell.model.coupon import STANDARD_AREA_M2, Coupon, CouponReading
from dropcell.model.segment import Segment


def coupon(**overrides: object) -> Coupon:
    kwargs: dict[str, object] = {
        "code": "CP-4",
        "test_point_code": "TP-114",
        "area_m2": STANDARD_AREA_M2,
        "shunt_ohm": 0.01,
        "installed_on": dt.date(2019, 6, 3),
    }
    kwargs.update(overrides)
    return Coupon(**kwargs)  # type: ignore[arg-type]


def reading(**overrides: object) -> CouponReading:
    kwargs: dict[str, object] = {
        "coupon_code": "CP-4",
        "taken_on": dt.date(2025, 3, 14),
        "on_mv": -1120.0,
        "disconnected_mv": -905.0,
    }
    kwargs.update(overrides)
    return CouponReading(**kwargs)  # type: ignore[arg-type]


def test_a_coupon_with_no_ac_is_judged_on_the_ordinary_set(segment: Segment) -> None:
    result = assess_coupon(coupon(), reading(), segment)
    assert result.protected
    assert result.ac_density_a_per_m2 is None
    assert "ac_current_density" not in [item.criterion for item in result.verdict.limits]


def test_a_coupon_carrying_ac_is_judged_with_the_ac_limits(segment: Segment) -> None:
    result = assess_coupon(coupon(), reading(ac_shunt_mv=0.005), segment)
    keys = [item.criterion for item in result.verdict.limits]
    assert "ac_current_density" in keys


def test_the_densities_come_off_the_shunt_drops(segment: Segment) -> None:
    result = assess_coupon(coupon(), reading(dc_shunt_mv=0.001, ac_shunt_mv=0.01), segment)
    assert result.dc_density_a_per_m2 == pytest.approx(1.0)
    assert result.ac_density_a_per_m2 == pytest.approx(10.0)


def test_the_ratio_needs_both_densities(segment: Segment) -> None:
    assert assess_coupon(coupon(), reading(), segment).ac_to_dc_ratio is None
    both = assess_coupon(coupon(), reading(dc_shunt_mv=0.001, ac_shunt_mv=0.01), segment)
    assert both.ac_to_dc_ratio == pytest.approx(10.0)


def test_a_zero_dc_density_leaves_the_ratio_unknown(segment: Segment) -> None:
    result = assess_coupon(coupon(), reading(dc_shunt_mv=0.0, ac_shunt_mv=0.01), segment)
    assert result.ac_to_dc_ratio is None


def test_a_protected_coupon_taking_too_much_ac_looks_fine_on_potential_alone(
    segment: Segment,
) -> None:
    result = assess_coupon(coupon(), reading(ac_shunt_mv=0.15), segment)
    assert result.ac_density_a_per_m2 == pytest.approx(150.0)
    assert result.protected
    assert result.has_findings
    assert result.looks_fine_on_potential_alone


def test_a_quiet_coupon_does_not_trip_that_flag(segment: Segment) -> None:
    result = assess_coupon(coupon(), reading(ac_shunt_mv=0.0001), segment)
    assert result.protected
    assert not result.looks_fine_on_potential_alone


def test_a_coupon_under_criterion_is_not_hiding_anything(segment: Segment) -> None:
    result = assess_coupon(coupon(), reading(disconnected_mv=-700.0), segment)
    assert not result.protected
    assert not result.looks_fine_on_potential_alone


def test_a_criterion_set_can_be_forced(segment: Segment) -> None:
    result = assess_coupon(
        coupon(), reading(ac_shunt_mv=0.02), segment, criterion_set=IMPRESSED_CURRENT
    )
    keys = [item.criterion for item in result.verdict.limits]
    assert "ac_current_density" not in keys


def test_the_evidence_carries_the_segment_resistivity(segment: Segment) -> None:
    wet = dataclasses.replace(segment, soil_resistivity_ohm_m=8.0)
    evidence = build_evidence(coupon(), reading(), wet)
    assert evidence.soil_resistivity_ohm_m == pytest.approx(8.0)
    assert evidence.label == "CP-4"


def test_a_disconnected_reading_counts_as_interrupted(segment: Segment) -> None:
    assert build_evidence(coupon(), reading(), segment).interrupted
    assert not build_evidence(coupon(), reading(disconnected_mv=None), segment).interrupted


def test_the_assessment_carries_the_date_and_the_code(segment: Segment) -> None:
    result = assess_coupon(coupon(), reading(), segment)
    assert result.code == "CP-4"
    assert result.taken_on == dt.date(2025, 3, 14)


def test_ordering_puts_the_most_ac_first(segment: Segment) -> None:
    quiet = assess_coupon(coupon(code="CP-1"), reading(ac_shunt_mv=0.0001), segment)
    loud = assess_coupon(coupon(code="CP-2"), reading(ac_shunt_mv=0.02), segment)
    assert [item.code for item in worst_first([quiet, loud])] == ["CP-2", "CP-1"]


def test_a_coupon_with_no_ac_sorts_last(segment: Segment) -> None:
    none = assess_coupon(coupon(code="CP-1"), reading(), segment)
    some = assess_coupon(coupon(code="CP-2"), reading(ac_shunt_mv=0.001), segment)
    assert [item.code for item in worst_first([none, some])] == ["CP-2", "CP-1"]
