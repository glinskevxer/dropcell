from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.model.coupon import STANDARD_AREA_M2, Coupon, CouponOrientation, CouponReading


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
    }
    kwargs.update(overrides)
    return CouponReading(**kwargs)  # type: ignore[arg-type]


def test_codes_are_normalised() -> None:
    made = coupon(code="cp 4", test_point_code="tp-114")
    assert (made.code, made.test_point_code) == ("CP-4", "TP-114")


@pytest.mark.parametrize("area", [0.0, -1e-4])
def test_a_coupon_with_no_area_is_refused(area: float) -> None:
    with pytest.raises(ValidationError):
        coupon(area_m2=area)


def test_a_shunt_with_no_resistance_is_refused() -> None:
    with pytest.raises(ValidationError):
        coupon(shunt_ohm=0.0)


def test_a_coupon_at_no_depth_is_refused() -> None:
    with pytest.raises(ValidationError):
        coupon(depth_m=0.0)


def test_the_area_converts_to_the_unit_it_was_sold_in() -> None:
    assert coupon().area_cm2 == pytest.approx(1.0)
    assert coupon(area_m2=6.45e-4).area_cm2 == pytest.approx(6.45)


def test_the_standard_coupon_is_recognised() -> None:
    assert coupon().is_standard_area
    assert not coupon(area_m2=6.45e-4).is_standard_area


def test_current_comes_off_the_shunt_by_ohms_law() -> None:
    assert coupon().current_a(1.0) == pytest.approx(0.1)
    assert coupon(shunt_ohm=0.1).current_a(1.0) == pytest.approx(0.01)


def test_density_divides_the_current_by_the_area() -> None:
    assert coupon().density_a_per_m2(0.01) == pytest.approx(10.0)


def test_a_coupon_of_twice_the_area_reads_half_the_density() -> None:
    small = coupon().density_a_per_m2(0.01)
    large = coupon(area_m2=2 * STANDARD_AREA_M2).density_a_per_m2(0.01)
    assert large == pytest.approx(small / 2)


def test_only_the_bottom_coupon_is_the_pessimistic_one() -> None:
    assert CouponOrientation.BOTTOM.represents_worst_case
    assert not CouponOrientation.TOP.represents_worst_case
    assert not CouponOrientation.SIDE.represents_worst_case


def test_a_reading_without_a_disconnected_potential_is_not_ir_free() -> None:
    assert not reading().is_ir_free
    assert reading().ir_drop_mv is None


def test_disconnecting_the_coupon_gives_an_ir_free_potential() -> None:
    taken = reading(disconnected_mv=-905.0)
    assert taken.is_ir_free
    assert taken.ir_drop_mv == pytest.approx(-215.0)


def test_an_impossible_potential_is_refused() -> None:
    with pytest.raises(ValidationError):
        reading(on_mv=-9000.0)
    with pytest.raises(ValidationError):
        reading(disconnected_mv=4000.0)


def test_a_negative_ac_voltage_is_refused() -> None:
    with pytest.raises(ValidationError):
        reading(ac_voltage_v=-1.0)


def test_the_comment_stays_out_of_equality() -> None:
    assert reading(comment="shunt corroded") == reading()
