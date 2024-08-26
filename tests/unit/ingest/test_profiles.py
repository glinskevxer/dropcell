from __future__ import annotations

import pytest

from dropcell.errors import IngestError
from dropcell.ingest.mapping import FieldType
from dropcell.ingest.profiles import (
    ANNUAL_PROFILE,
    CIS_PROFILE,
    DCVG_PROFILE,
    PROFILES,
    RECTIFIER_PROFILE,
    SOIL_PROFILE,
    get_profile,
    profile_names,
)
from dropcell.ingest.reader import read_text


def test_every_profile_is_registered_under_its_own_name() -> None:
    for name, profile in PROFILES.items():
        assert profile.name == name


def test_the_names_come_back_sorted() -> None:
    assert profile_names() == sorted(PROFILES)


def test_a_profile_can_be_looked_up() -> None:
    assert get_profile("cis") is CIS_PROFILE


def test_an_unknown_profile_lists_the_ones_that_exist() -> None:
    with pytest.raises(IngestError) as caught:
        get_profile("wishful")
    assert "cis" in caught.value.detail["known"]


def test_every_profile_describes_itself() -> None:
    for profile in PROFILES.values():
        assert profile.description


def test_no_profile_requires_a_column_with_a_default() -> None:
    for profile in PROFILES.values():
        for column in profile.columns:
            assert not (column.required and column.default is not None)


def test_the_close_interval_profile_takes_three_spellings_of_the_same_file() -> None:
    variants = [
        "Station,P/S On,P/S Off\n0+00.00,-1120,-905\n",
        "CHAINAGE,ON POTENTIAL,INSTANT OFF\n0+00.00,-1120,-905\n",
        "Sta,On_mV,Off_mV\n0+00.00,-1120,-905\n",
    ]
    for text in variants:
        result = read_text(text, CIS_PROFILE)
        assert result.accepted == 1
        assert result.rows[0]["off_mv"] == pytest.approx(-905.0)


def test_the_close_interval_profile_reads_a_file_with_no_off_column() -> None:
    result = read_text("Station,On\n0+00.00,-1120\n", CIS_PROFILE)
    assert result.accepted == 1
    assert result.rows[0]["off_mv"] is None


def test_the_annual_profile_needs_a_post_a_date_and_an_on_reading() -> None:
    assert set(ANNUAL_PROFILE.required_fields) == {"test_point_code", "taken_on", "on_mv"}


def test_the_annual_profile_reads_a_full_row() -> None:
    text = (
        "Test Post,Date,Lead,On,Off,Native,Half Cell,Surveyor\n"
        "TP-114,2025-03-14,pipe,-1120,-905,-580,CSE-114,R Ellis\n"
    )
    row = read_text(text, ANNUAL_PROFILE).rows[0]
    assert row["test_point_code"] == "TP-114"
    assert row["native_mv"] == pytest.approx(-580.0)
    assert row["technician"] == "R Ellis"


def test_the_rectifier_profile_reads_volts_and_amps_in_their_own_units() -> None:
    text = "Rectifier,Date,Volts,Amps,Coarse,Fine\nRU-3,2025-03-14,18.5 V,12.4 A,3,2\n"
    row = read_text(text, RECTIFIER_PROFILE).rows[0]
    assert row["output_voltage_v"] == pytest.approx(18.5)
    assert row["output_current_a"] == pytest.approx(12.4)
    assert row["coarse_tap"] == 3


def test_a_rectifier_current_written_in_milliamps_still_lands_in_amps() -> None:
    text = "Unit,Date,V,A\nRU-3,2025-03-14,18.5,250 mA\n"
    row = read_text(text, RECTIFIER_PROFILE).rows[0]
    assert row["output_current_a"] == pytest.approx(0.25)


def test_the_gradient_profile_reads_the_anodic_flag_however_it_is_written() -> None:
    text = (
        "Station,Date,Gradient,Total Shift,Anodic\n"
        "12+45.50,2025-03-14,40,400,y\n"
        "14+00.00,2025-03-14,60,400,\n"
    )
    rows = read_text(text, DCVG_PROFILE).rows
    assert rows[0]["anodic"] is True
    assert rows[1]["anodic"] is False


def test_the_soil_profile_reads_a_sounding_row() -> None:
    text = "Station,Date,Pin Spacing,Resistance\n12+45.50,2025-03-14,1.5 m,4.2\n"
    row = read_text(text, SOIL_PROFILE).rows[0]
    assert row["spacing_m"] == pytest.approx(1.5)
    assert row["resistance_ohm"] == pytest.approx(4.2)


def test_a_soil_spacing_in_feet_lands_in_metres() -> None:
    text = "Station,Date,A,R\n12+45.50,2025-03-14,5 ft,4.2\n"
    row = read_text(text, SOIL_PROFILE).rows[0]
    assert row["spacing_m"] == pytest.approx(1.524)


def test_every_profile_declares_a_type_for_every_column() -> None:
    for profile in PROFILES.values():
        for column in profile.columns:
            assert isinstance(column.field_type, FieldType)
