from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.model.coupon import STANDARD_AREA_M2, Coupon, CouponOrientation, CouponReading
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station
from dropcell.store.coupons import CouponReadingRepository, CouponRepository
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.testpoints import TestPointRepository


@pytest.fixture
def wired(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    posts = TestPointRepository(database)
    for code, metres in (("TP-114", 1245.5), ("TP-115", 2400.0)):
        posts.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(metres),
                leads=frozenset({LeadKind.PIPE, LeadKind.COUPON}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
    return database


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


def test_a_coupon_survives_a_round_trip(wired: Database) -> None:
    coupons = CouponRepository(wired)
    original = coupon(orientation=CouponOrientation.BOTTOM, description="south side")
    coupons.add(original)
    assert coupons.get("CP-4") == original


def test_a_coupon_on_a_post_that_is_not_there_is_refused(wired: Database) -> None:
    with pytest.raises(ConflictError):
        CouponRepository(wired).add(coupon(test_point_code="TP-999"))


def test_coupons_can_be_found_by_post(wired: Database) -> None:
    coupons = CouponRepository(wired)
    coupons.add(coupon())
    coupons.add(coupon(code="CP-5", test_point_code="TP-115"))
    assert [item.code for item in coupons.for_post("TP-114")] == ["CP-4"]


def test_coupons_on_a_line_come_back_in_stationing_order(wired: Database) -> None:
    coupons = CouponRepository(wired)
    coupons.add(coupon(code="CP-5", test_point_code="TP-115"))
    coupons.add(coupon())
    assert [item.code for item in coupons.for_line("AL-2")] == ["CP-4", "CP-5"]


def test_a_missing_coupon_is_named_in_the_refusal(wired: Database) -> None:
    with pytest.raises(NotFoundError) as caught:
        CouponRepository(wired).get("CP-9")
    assert caught.value.detail["code"] == "CP-9"


def test_a_reading_survives_a_round_trip(wired: Database) -> None:
    CouponRepository(wired).add(coupon())
    readings = CouponReadingRepository(wired)
    original = reading(disconnected_mv=-905.0, dc_shunt_mv=0.001, ac_shunt_mv=0.01)
    readings.add(original)
    assert readings.for_coupon("CP-4") == [original]


def test_two_readings_on_one_coupon_in_a_day_are_refused(wired: Database) -> None:
    CouponRepository(wired).add(coupon())
    readings = CouponReadingRepository(wired)
    readings.add(reading())
    with pytest.raises(ConflictError):
        readings.add(reading(on_mv=-1100.0))


def test_a_reading_on_a_coupon_that_is_not_there_is_refused(wired: Database) -> None:
    with pytest.raises(ConflictError):
        CouponReadingRepository(wired).add(reading())


def test_the_latest_reading_is_the_most_recent(wired: Database) -> None:
    CouponRepository(wired).add(coupon())
    readings = CouponReadingRepository(wired)
    readings.add(reading(taken_on=dt.date(2024, 1, 1)))
    readings.add(reading())
    latest = readings.latest("CP-4")
    assert latest is not None
    assert latest.taken_on == dt.date(2025, 3, 14)


def test_a_coupon_never_read_has_no_latest(wired: Database) -> None:
    CouponRepository(wired).add(coupon())
    assert CouponReadingRepository(wired).latest("CP-4") is None


def test_a_batch_reports_how_many_landed(wired: Database) -> None:
    CouponRepository(wired).add(coupon())
    readings = CouponReadingRepository(wired)
    assert readings.add_many([reading(), reading(taken_on=dt.date(2024, 1, 1))]) == 2
    assert readings.count() == 2


def test_deleting_a_post_takes_its_coupons_and_their_readings(wired: Database) -> None:
    CouponRepository(wired).add(coupon())
    CouponReadingRepository(wired).add(reading())
    TestPointRepository(wired).delete("TP-114")
    assert CouponRepository(wired).count() == 0
    assert CouponReadingRepository(wired).count() == 0
