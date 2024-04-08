from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.model.rectifier import Rectifier, RectifierCheck
from dropcell.stationing import Station


def make_rectifier(**overrides: object) -> Rectifier:
    kwargs: dict[str, object] = {
        "tag": "RU-3",
        "line_code": "AL-2",
        "station": Station(4210.0),
        "groundbed_code": "GB-3",
        "rated_voltage_v": 24.0,
        "rated_current_a": 20.0,
        "coarse_taps": 5,
        "fine_taps": 4,
        "installed_on": dt.date(2004, 9, 1),
    }
    kwargs.update(overrides)
    return Rectifier(**kwargs)  # type: ignore[arg-type]


def make_check(**overrides: object) -> RectifierCheck:
    kwargs: dict[str, object] = {
        "rectifier_tag": "RU-3",
        "checked_on": dt.date(2025, 3, 14),
        "output_voltage_v": 18.5,
        "output_current_a": 12.4,
        "coarse_tap": 3,
        "fine_tap": 2,
    }
    kwargs.update(overrides)
    return RectifierCheck(**kwargs)  # type: ignore[arg-type]


def test_a_rectifier_normalises_all_three_codes() -> None:
    unit = make_rectifier(tag="ru 3", line_code="al-2", groundbed_code="gb_3")
    assert (unit.tag, unit.line_code, unit.groundbed_code) == ("RU-3", "AL-2", "GB-3")


@pytest.mark.parametrize(("volts", "amps"), [(0.0, 20.0), (24.0, 0.0), (-5.0, 20.0)])
def test_a_rectifier_with_no_rating_is_refused(volts: float, amps: float) -> None:
    with pytest.raises(ValidationError):
        make_rectifier(rated_voltage_v=volts, rated_current_a=amps)


@pytest.mark.parametrize(("coarse", "fine"), [(0, 4), (5, 0), (-1, 4)])
def test_tap_counts_start_at_one(coarse: int, fine: int) -> None:
    with pytest.raises(ValidationError):
        make_rectifier(coarse_taps=coarse, fine_taps=fine)


def test_the_nameplate_power_is_volts_times_amps() -> None:
    assert make_rectifier().rated_power_w == pytest.approx(480.0)


def test_the_board_offers_the_product_of_the_two_tap_counts() -> None:
    assert make_rectifier().tap_positions == 20


def test_a_tap_off_the_end_of_the_board_is_not_valid() -> None:
    unit = make_rectifier()
    assert unit.is_valid_tap(5, 4)
    assert not unit.is_valid_tap(6, 4)
    assert not unit.is_valid_tap(5, 5)
    assert not unit.is_valid_tap(0, 1)


def test_a_check_refuses_negative_output() -> None:
    with pytest.raises(ValidationError):
        make_check(output_current_a=-1.0)
    with pytest.raises(ValidationError):
        make_check(output_voltage_v=-1.0)


def test_a_check_refuses_a_negative_hour_meter() -> None:
    with pytest.raises(ValidationError):
        make_check(hour_meter=-3.0)


def test_output_power_is_read_off_the_two_panel_meters() -> None:
    assert make_check().output_power_w == pytest.approx(229.4)


def test_a_unit_drawing_nothing_reads_as_off() -> None:
    assert make_check(output_current_a=0.0).is_off
    assert make_check(output_current_a=0.05).is_off
    assert not make_check(output_current_a=0.06).is_off


def test_circuit_resistance_is_only_meaningful_while_current_flows() -> None:
    assert make_check().circuit_resistance_ohm == pytest.approx(18.5 / 12.4)
    assert make_check(output_current_a=0.0).circuit_resistance_ohm is None


def test_load_fraction_is_output_against_the_nameplate() -> None:
    assert make_check().load_fraction(make_rectifier()) == pytest.approx(0.62)


def test_a_unit_at_most_of_its_rating_is_near_capacity() -> None:
    unit = make_rectifier()
    assert make_check(output_current_a=17.0).is_near_capacity(unit)
    assert not make_check(output_current_a=16.9).is_near_capacity(unit)


def test_a_tap_written_on_the_sheet_is_checked_against_the_board() -> None:
    unit = make_rectifier()
    assert make_check().tap_is_valid_for(unit)
    assert not make_check(coarse_tap=9).tap_is_valid_for(unit)


def test_the_comment_stays_out_of_equality() -> None:
    assert make_check(comment="fuse holder corroded") == make_check()
