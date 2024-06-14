from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.interference.foreign import (
    Crossing,
    InterferenceVerdict,
    SwingTest,
    bond_resistance_ohm,
    classify_swing,
)
from dropcell.stationing import Station


def swing(**overrides: object) -> SwingTest:
    kwargs: dict[str, object] = {
        "crossing_code": "XG-4",
        "tested_on": dt.date(2025, 3, 14),
        "foreign_with_ours_on_mv": -700.0,
        "foreign_with_ours_off_mv": -760.0,
    }
    kwargs.update(overrides)
    return SwingTest(**kwargs)  # type: ignore[arg-type]


def test_a_crossing_normalises_its_codes_and_trims_the_operator() -> None:
    crossing = Crossing(
        code="xg 4",
        line_code="al-2",
        station=Station(1245.5),
        foreign_operator="  Vale Water  ",
        foreign_structure="18 inch water main",
    )
    assert (crossing.code, crossing.line_code) == ("XG-4", "AL-2")
    assert crossing.foreign_operator == "Vale Water"


def test_a_crossing_with_no_foreign_operator_is_refused() -> None:
    with pytest.raises(ValidationError):
        Crossing(
            code="XG-4",
            line_code="AL-2",
            station=Station(0.0),
            foreign_operator="   ",
            foreign_structure="water main",
        )


def test_a_positive_swing_means_current_is_leaving_their_steel() -> None:
    result = classify_swing(swing())
    assert result.verdict is InterferenceVerdict.HARMING_FOREIGN
    assert result.foreign_swing_mv == pytest.approx(60.0)
    assert result.verdict.needs_mitigation
    assert result.verdict.is_our_liability


def test_a_negative_swing_means_they_are_getting_protection_for_nothing() -> None:
    result = classify_swing(
        swing(foreign_with_ours_on_mv=-880.0, foreign_with_ours_off_mv=-620.0)
    )
    assert result.verdict is InterferenceVerdict.BENEFICIAL
    assert not result.verdict.needs_mitigation


def test_a_swing_inside_the_limit_is_nothing_to_argue_about() -> None:
    result = classify_swing(
        swing(foreign_with_ours_on_mv=-755.0, foreign_with_ours_off_mv=-760.0)
    )
    assert result.verdict is InterferenceVerdict.NONE
    assert not result.verdict.needs_mitigation


def test_a_swing_exactly_on_the_limit_is_still_nothing() -> None:
    result = classify_swing(
        swing(foreign_with_ours_on_mv=-740.0, foreign_with_ours_off_mv=-760.0)
    )
    assert result.verdict is InterferenceVerdict.NONE


def test_the_limit_can_be_tightened() -> None:
    reading = swing(foreign_with_ours_on_mv=-755.0, foreign_with_ours_off_mv=-760.0)
    assert classify_swing(reading, limit_mv=2.0).verdict is InterferenceVerdict.HARMING_FOREIGN


def test_a_limit_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        classify_swing(swing(), limit_mv=0.0)


def test_a_swing_found_with_their_unit_off_is_their_current() -> None:
    result = classify_swing(swing(their_rectifier_interrupted=True))
    assert result.verdict is InterferenceVerdict.HARMED_BY_FOREIGN
    assert result.verdict.needs_mitigation
    assert not result.verdict.is_our_liability


def test_our_own_swing_needs_both_of_our_readings() -> None:
    assert swing().our_swing_mv is None
    assert swing(ours_on_mv=-1120.0).our_swing_mv is None
    both = swing(ours_on_mv=-1120.0, ours_off_mv=-905.0)
    assert both.our_swing_mv == pytest.approx(-215.0)


def test_the_crossing_code_is_normalised_on_a_test_too() -> None:
    assert swing(crossing_code="xg 4").crossing_code == "XG-4"


def test_an_impossible_potential_is_refused() -> None:
    with pytest.raises(ValidationError):
        swing(foreign_with_ours_on_mv=-9000.0)
    with pytest.raises(ValidationError):
        swing(ours_off_mv=4000.0)


def test_a_bond_resistor_follows_ohms_law_on_the_swing() -> None:
    assert bond_resistance_ohm(60.0, 2.0) == pytest.approx(0.03)
    assert bond_resistance_ohm(120.0, 2.0) == pytest.approx(0.06)


def test_a_bond_cannot_be_sized_against_nothing() -> None:
    with pytest.raises(ValidationError):
        bond_resistance_ohm(60.0, 0.0)
    with pytest.raises(ValidationError):
        bond_resistance_ohm(-60.0, 2.0)
