from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError
from dropcell.ingest.coupon import import_coupon_readings
from dropcell.model.coupon import STANDARD_AREA_M2, Coupon
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station
from dropcell.store.coupons import CouponReadingRepository, CouponRepository
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.testpoints import TestPointRepository

NOW = dt.datetime(2025, 3, 20, 9, 0)
HEADER = "Coupon,Date,On,Disconnected,DC Shunt,AC Shunt,AC Volts,Tech,Comment\n"
GOOD = (
    HEADER
    + "CP-4,2025-03-14,-1120,-905,0.001,0.01,3.2,R Ellis,\n"
    + "CP-5,2025-03-14,-1080,-870,0.002,0.05,6.4,R Ellis,\n"
)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    TestPointRepository(database).add(
        TestPoint(
            code="TP-114",
            line_code="AL-2",
            station=Station(1245.5),
            leads=frozenset({LeadKind.PIPE, LeadKind.COUPON}),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    coupons = CouponRepository(database)
    for code in ("CP-4", "CP-5"):
        coupons.add(
            Coupon(
                code=code,
                test_point_code="TP-114",
                area_m2=STANDARD_AREA_M2,
                shunt_ohm=0.01,
                installed_on=dt.date(2019, 6, 3),
            )
        )
    return database


def test_a_clean_file_lands_every_row(register: Database) -> None:
    loaded = import_coupon_readings(register, GOOD, now=NOW, source="coupons.csv")
    assert loaded.written == 2
    assert loaded.clean
    assert CouponReadingRepository(register).count() == 2


def test_the_readings_carry_what_the_file_said(register: Database) -> None:
    import_coupon_readings(register, GOOD, now=NOW)
    stored = CouponReadingRepository(register).for_coupon("CP-4")[0]
    assert stored.on_mv == pytest.approx(-1120.0)
    assert stored.dc_shunt_mv == pytest.approx(0.001)
    assert stored.ac_voltage_v == pytest.approx(3.2)
    assert stored.technician == "R Ellis"


def test_the_shunts_are_millivolts_and_the_ac_is_volts(register: Database) -> None:
    import_coupon_readings(register, GOOD, now=NOW)
    stored = CouponReadingRepository(register).for_coupon("CP-5")[0]
    assert stored.ac_shunt_mv == pytest.approx(0.05)
    assert stored.ac_voltage_v == pytest.approx(6.4)


def test_a_row_naming_a_coupon_that_is_not_there_is_reported(
    register: Database,
) -> None:
    text = HEADER + "CP-9,2025-03-14,-1120,,,,,,\n"
    loaded = import_coupon_readings(register, text, now=NOW)
    assert loaded.written == 0
    assert "no coupon with that code" in loaded.reasons()[0]


def test_a_row_with_nothing_but_a_connected_potential_is_called_thin(
    register: Database,
) -> None:
    text = HEADER + "CP-4,2025-03-14,-1120,,,,,,\n"
    loaded = import_coupon_readings(register, text, now=NOW)
    assert loaded.written == 1
    assert loaded.thin == ("CP-4 on 2025-03-14",)


def test_a_row_with_a_shunt_is_not_thin(register: Database) -> None:
    loaded = import_coupon_readings(register, GOOD, now=NOW)
    assert loaded.thin == ()


def test_a_reading_already_in_the_register_is_skipped(register: Database) -> None:
    import_coupon_readings(register, GOOD, now=NOW)
    resent = GOOD + "CP-4,2025-04-02,-1130,-910,,,,,\n"
    loaded = import_coupon_readings(register, resent, now=NOW)
    assert loaded.written == 1
    assert all("already in the register" in reason for reason in loaded.reasons())


def test_a_file_that_reads_one_coupon_twice_in_a_day_keeps_the_first(
    register: Database,
) -> None:
    text = GOOD + "CP-4,2025-03-14,-1000,,,,,,\n"
    loaded = import_coupon_readings(register, text, now=NOW)
    assert loaded.written == 2
    assert "twice on one day" in loaded.reasons()[0]


def test_the_same_file_twice_is_a_conflict(register: Database) -> None:
    import_coupon_readings(register, GOOD, now=NOW)
    with pytest.raises(ConflictError):
        import_coupon_readings(register, GOOD, now=NOW)


def test_a_broken_row_is_quarantined_and_counted(register: Database) -> None:
    text = GOOD + "CP-4,not a date,-1120,,,,,,\n"
    loaded = import_coupon_readings(register, text, now=NOW)
    assert loaded.quarantined == 1
    assert not loaded.clean


def test_a_coupon_code_written_untidily_still_matches(register: Database) -> None:
    text = HEADER + "cp 4,2025-03-14,-1120,-905,,,,,\n"
    assert import_coupon_readings(register, text, now=NOW).written == 1


def test_the_run_is_written_to_the_ledger(register: Database) -> None:
    loaded = import_coupon_readings(register, GOOD, now=NOW, source="coupons.csv")
    assert loaded.run.kind == "coupon"
    assert loaded.run.accepted == 2
