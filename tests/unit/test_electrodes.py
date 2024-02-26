from __future__ import annotations

import datetime as dt

import pytest

from dropcell.electrodes import (
    CALIBRATION_REJECT_MV,
    ELECTRODE_NAMES,
    SHE_MILLIVOLTS,
    CellCheck,
    Electrode,
    convert_potential,
    to_cse,
)
from dropcell.errors import ValidationError


def test_converting_to_the_same_electrode_changes_nothing() -> None:
    assert convert_potential(-850.0, Electrode.CSE, Electrode.CSE) == pytest.approx(-850.0)


def test_a_copper_sulfate_reading_is_less_negative_against_calomel() -> None:
    assert convert_potential(-850.0, Electrode.CSE, Electrode.SCE) == pytest.approx(-773.0)


def test_a_calomel_reading_is_more_negative_against_copper_sulfate() -> None:
    assert to_cse(-773.0, Electrode.SCE) == pytest.approx(-850.0)


def test_silver_chloride_converts_both_ways_without_drift() -> None:
    there = convert_potential(-900.0, Electrode.CSE, Electrode.SILVER_CHLORIDE)
    back = convert_potential(there, Electrode.SILVER_CHLORIDE, Electrode.CSE)
    assert back == pytest.approx(-900.0)


def test_a_zinc_cell_reading_is_a_positive_number_against_copper_sulfate() -> None:
    assert to_cse(50.0, Electrode.ZINC_SEAWATER) == pytest.approx(-1048.0)


def test_every_electrode_carries_a_potential_and_a_name() -> None:
    for electrode in Electrode:
        assert electrode in SHE_MILLIVOLTS
        assert ELECTRODE_NAMES[electrode]


def test_a_check_expires_a_fixed_number_of_days_after_it_was_taken() -> None:
    check = CellCheck("CSE-114", dt.date(2025, 1, 10), offset_mv=3.0)
    assert check.expires_on == dt.date(2025, 7, 9)


def test_a_check_covers_readings_between_the_check_and_its_expiry() -> None:
    check = CellCheck("CSE-114", dt.date(2025, 1, 10), offset_mv=3.0, valid_days=90)
    assert check.covers(dt.date(2025, 1, 10))
    assert check.covers(dt.date(2025, 3, 1))
    assert check.covers(dt.date(2025, 4, 10))
    assert not check.covers(dt.date(2025, 4, 11))
    assert not check.covers(dt.date(2025, 1, 9))


def test_correcting_takes_the_cell_error_back_out() -> None:
    check = CellCheck("CSE-114", dt.date(2025, 1, 10), offset_mv=8.0)
    assert check.correct(-842.0) == pytest.approx(-850.0)


def test_a_cell_inside_tolerance_stays_in_service() -> None:
    check = CellCheck("CSE-114", dt.date(2025, 1, 10), offset_mv=CALIBRATION_REJECT_MV)
    assert check.within_tolerance


def test_a_cell_outside_tolerance_will_not_correct_anything() -> None:
    check = CellCheck("CSE-9", dt.date(2025, 1, 10), offset_mv=-31.0)
    assert not check.within_tolerance
    with pytest.raises(ValidationError) as caught:
        check.correct(-880.0)
    assert caught.value.detail["serial"] == "CSE-9"


def test_a_blank_serial_is_refused() -> None:
    with pytest.raises(ValidationError):
        CellCheck("   ", dt.date(2025, 1, 10), offset_mv=0.0)


@pytest.mark.parametrize("days", [0, -30])
def test_a_non_positive_validity_is_refused(days: int) -> None:
    with pytest.raises(ValidationError):
        CellCheck("CSE-114", dt.date(2025, 1, 10), offset_mv=0.0, valid_days=days)
