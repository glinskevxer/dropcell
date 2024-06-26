from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.interference.bonds import (
    Bond,
    BondCheck,
    BondHealth,
    BondKind,
    assess_bond,
    critical_bonds,
    overdue_bonds,
)
from dropcell.stationing import Station


def bond(**overrides: object) -> Bond:
    kwargs: dict[str, object] = {
        "code": "BD-7",
        "line_code": "AL-2",
        "station": Station(1245.5),
        "kind": BondKind.RESISTIVE,
        "to_structure": "Vale Water 18 inch main",
        "installed_on": dt.date(2011, 4, 2),
        "design_current_a": 2.0,
        "resistor_ohm": 0.03,
    }
    kwargs.update(overrides)
    return Bond(**kwargs)  # type: ignore[arg-type]


def check(**overrides: object) -> BondCheck:
    kwargs: dict[str, object] = {
        "bond_code": "BD-7",
        "checked_on": dt.date(2025, 3, 14),
        "current_a": 2.0,
    }
    kwargs.update(overrides)
    return BondCheck(**kwargs)  # type: ignore[arg-type]


def test_codes_are_normalised_and_the_structure_is_trimmed() -> None:
    made = bond(code="bd 7", line_code="al-2", to_structure="  water main  ")
    assert (made.code, made.line_code) == ("BD-7", "AL-2")
    assert made.to_structure == "water main"


def test_a_bond_with_nowhere_to_go_is_refused() -> None:
    with pytest.raises(ValidationError):
        bond(to_structure="  ")


def test_a_bond_with_no_design_current_is_refused() -> None:
    with pytest.raises(ValidationError):
        bond(design_current_a=0.0)


def test_a_resistive_bond_without_its_resistor_is_refused() -> None:
    with pytest.raises(ValidationError):
        bond(resistor_ohm=None)


def test_a_direct_bond_needs_no_resistor() -> None:
    assert bond(kind=BondKind.DIRECT, resistor_ohm=None).resistor_ohm is None


def test_a_resistor_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        bond(resistor_ohm=0.0)


def test_only_the_switched_kinds_block_one_direction() -> None:
    assert BondKind.DIODE.is_one_way
    assert BondKind.REVERSE_CURRENT_SWITCH.is_one_way
    assert not BondKind.DIRECT.is_one_way
    assert not BondKind.RESISTIVE.is_one_way


def test_a_critical_bond_is_read_on_the_rectifier_cycle() -> None:
    assert bond(critical=True).check_interval_days == 75
    assert bond().check_interval_days == 450


def test_a_bond_carrying_its_design_current_is_healthy() -> None:
    assert assess_bond(bond(), check()) is BondHealth.HEALTHY


def test_a_bond_carrying_nothing_is_open() -> None:
    assert assess_bond(bond(), check(current_a=0.0)) is BondHealth.OPEN
    assert assess_bond(bond(), check(current_a=0.005)) is BondHealth.OPEN


def test_a_bond_carrying_current_the_wrong_way_is_reversed() -> None:
    assert assess_bond(bond(), check(reversed_polarity=True)) is BondHealth.REVERSED


def test_an_open_bond_is_reported_as_open_even_if_it_is_also_reversed() -> None:
    reading = check(current_a=0.0, reversed_polarity=True)
    assert assess_bond(bond(), reading) is BondHealth.OPEN


def test_a_bond_well_off_its_design_current_is_out_of_range() -> None:
    assert assess_bond(bond(), check(current_a=0.5)) is BondHealth.OUT_OF_RANGE
    assert assess_bond(bond(), check(current_a=6.0)) is BondHealth.OUT_OF_RANGE


def test_the_tolerance_band_is_inclusive_at_both_ends() -> None:
    assert assess_bond(bond(), check(current_a=1.2)) is BondHealth.HEALTHY
    assert assess_bond(bond(), check(current_a=2.8)) is BondHealth.HEALTHY


def test_the_tolerance_can_be_tightened() -> None:
    assert assess_bond(bond(), check(current_a=2.5), tolerance=0.1) is BondHealth.OUT_OF_RANGE


@pytest.mark.parametrize("tolerance", [0.0, 1.0, -0.2])
def test_a_tolerance_that_is_not_a_fraction_is_refused(tolerance: float) -> None:
    with pytest.raises(ValidationError):
        assess_bond(bond(), check(), tolerance=tolerance)


def test_only_a_healthy_bond_is_not_a_fault() -> None:
    assert not BondHealth.HEALTHY.is_fault
    for health in (BondHealth.OPEN, BondHealth.REVERSED, BondHealth.OUT_OF_RANGE):
        assert health.is_fault


def test_critical_bonds_are_picked_out_of_a_list() -> None:
    ordinary = bond()
    important = bond(code="BD-8", critical=True)
    assert critical_bonds([ordinary, important]) == [important]


def test_a_bond_never_checked_is_the_most_overdue_of_all() -> None:
    never = bond(code="BD-9")
    late = bond(code="BD-7")
    result = overdue_bonds(
        [late, never],
        {"BD-7": dt.date(2023, 1, 1)},
        dt.date(2025, 3, 14),
    )
    assert [item.code for item in result] == ["BD-9", "BD-7"]


def test_a_bond_inside_its_interval_is_not_overdue() -> None:
    fresh = bond()
    result = overdue_bonds([fresh], {"BD-7": dt.date(2025, 1, 1)}, dt.date(2025, 3, 14))
    assert result == []


def test_a_critical_bond_goes_overdue_sooner_than_an_ordinary_one() -> None:
    ordinary = bond()
    important = dataclasses.replace(ordinary, code="BD-8", critical=True)
    checked = {"BD-7": dt.date(2024, 12, 1), "BD-8": dt.date(2024, 12, 1)}
    result = overdue_bonds([ordinary, important], checked, dt.date(2025, 3, 14))
    assert [item.code for item in result] == ["BD-8"]
