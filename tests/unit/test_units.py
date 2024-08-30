from __future__ import annotations

import pytest

from dropcell.errors import UnitError
from dropcell.units import (
    current_density_a_per_m2,
    format_length_m,
    format_potential_mv,
    parse_area_m2,
    parse_current_a,
    parse_length_m,
    parse_potential_mv,
    parse_resistivity_ohm_m,
    parse_voltage_v,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("-912", -912.0),
        ("-912 mV", -912.0),
        ("-912mv", -912.0),
        ("-0.912 V", -912.0),
        ("-0.912V", -912.0),
        ("-1.204 volts", -1204.0),
        ("+43 mV", 43.0),
        ("  -850  ", -850.0),
    ],
)
def test_potentials_land_on_millivolts_whatever_the_logger_wrote(
    text: str, expected: float
) -> None:
    assert parse_potential_mv(text) == pytest.approx(expected)


def test_a_bare_potential_is_read_as_millivolts() -> None:
    assert parse_potential_mv("-1050") == pytest.approx(-1050.0)


def test_a_positive_potential_is_data_not_an_error() -> None:
    assert parse_potential_mv("0.115 V") == pytest.approx(115.0)


@pytest.mark.parametrize("text", ["", "mV", "abc", "-912 kV", "12 34", "--912"])
def test_junk_potentials_raise_a_unit_error(text: str) -> None:
    with pytest.raises(UnitError):
        parse_potential_mv(text)


def test_the_unit_error_names_what_it_would_have_accepted() -> None:
    with pytest.raises(UnitError) as caught:
        parse_potential_mv("-912 kV")
    assert caught.value.detail["unit"] == "kv"
    assert "mv" in caught.value.detail["known"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [("100 ft", 30.48), ("1 mi", 1609.344), ("2.5 km", 2500.0), ("18", 18.0)],
)
def test_lengths_land_on_metres(text: str, expected: float) -> None:
    assert parse_length_m(text) == pytest.approx(expected)


def test_currents_land_on_amperes() -> None:
    assert parse_current_a("250 mA") == pytest.approx(0.25)
    assert parse_current_a("14.2 A") == pytest.approx(14.2)
    assert parse_current_a("3") == pytest.approx(3.0)


def test_a_bare_area_is_read_as_square_centimetres() -> None:
    assert parse_area_m2("10") == pytest.approx(1e-3)
    assert parse_area_m2("6.45 cm2") == pytest.approx(6.45e-4)
    assert parse_area_m2("1 in2") == pytest.approx(0.00064516)


def test_a_bare_resistivity_is_read_as_ohm_centimetres() -> None:
    assert parse_resistivity_ohm_m("4500") == pytest.approx(45.0)
    assert parse_resistivity_ohm_m("45 ohm-m") == pytest.approx(45.0)
    assert parse_resistivity_ohm_m("4500 ohm.cm") == pytest.approx(45.0)


def test_current_density_divides_by_the_coupon_area() -> None:
    assert current_density_a_per_m2(0.001, 1e-4) == pytest.approx(10.0)


@pytest.mark.parametrize("area", [0.0, -1e-4])
def test_current_density_refuses_a_non_positive_area(area: float) -> None:
    with pytest.raises(UnitError):
        current_density_a_per_m2(0.001, area)


def test_potential_formatting_defaults_to_whole_millivolts() -> None:
    assert format_potential_mv(-912.4) == "-912 mV"
    assert format_potential_mv(-912.0, unit="V") == "-0.912 V"
    assert format_potential_mv(-912.0, unit="mV", places=1) == "-912.0 mV"


def test_length_formatting_converts_back_out_of_metres() -> None:
    assert format_length_m(30.48, unit="ft") == "100.00 ft"
    assert format_length_m(1609.344, unit="mi", places=3) == "1.000 mi"


def test_formatting_rejects_a_unit_it_cannot_convert() -> None:
    with pytest.raises(UnitError):
        format_potential_mv(-912.0, unit="kV")
    with pytest.raises(UnitError):
        format_length_m(10.0, unit="furlong")


def test_a_bare_supply_voltage_is_read_as_volts() -> None:
    assert parse_voltage_v("18.5") == pytest.approx(18.5)
    assert parse_voltage_v("18.5 V") == pytest.approx(18.5)
    assert parse_voltage_v("1200 mV") == pytest.approx(1.2)


def test_the_two_defaults_disagree_on_purpose() -> None:
    assert parse_potential_mv("18.5") == pytest.approx(18.5)
    assert parse_voltage_v("18.5") == pytest.approx(18.5)
    assert parse_potential_mv("18.5") != pytest.approx(parse_voltage_v("18.5") * 1000)


def test_an_unknown_supply_unit_is_refused() -> None:
    with pytest.raises(UnitError):
        parse_voltage_v("18.5 kV")
