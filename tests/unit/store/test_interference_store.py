from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.interference.bonds import Bond, BondKind
from dropcell.interference.foreign import Crossing
from dropcell.interference.isolation import IsolationJoint, JointKind
from dropcell.model.casing import Casing
from dropcell.model.line import Line
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.interference import (
    BondRepository,
    CasingRepository,
    CrossingRepository,
    IsolationJointRepository,
)
from dropcell.store.lines import LineRepository


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    return database


def casing(**overrides: object) -> Casing:
    kwargs: dict[str, object] = {
        "code": "CS-12",
        "line_code": "AL-2",
        "station": Station(1245.5),
        "installed_on": dt.date(1998, 5, 4),
    }
    kwargs.update(overrides)
    return Casing(**kwargs)  # type: ignore[arg-type]


def crossing(**overrides: object) -> Crossing:
    kwargs: dict[str, object] = {
        "code": "XG-4",
        "line_code": "AL-2",
        "station": Station(2400.0),
        "foreign_operator": "Vale Water",
        "foreign_structure": "18 inch water main",
    }
    kwargs.update(overrides)
    return Crossing(**kwargs)  # type: ignore[arg-type]


def bond(**overrides: object) -> Bond:
    kwargs: dict[str, object] = {
        "code": "BD-7",
        "line_code": "AL-2",
        "station": Station(2400.0),
        "kind": BondKind.RESISTIVE,
        "to_structure": "Vale Water 18 inch main",
        "installed_on": dt.date(2011, 4, 2),
        "design_current_a": 2.0,
        "resistor_ohm": 0.03,
    }
    kwargs.update(overrides)
    return Bond(**kwargs)  # type: ignore[arg-type]


def joint(**overrides: object) -> IsolationJoint:
    kwargs: dict[str, object] = {
        "code": "IJ-2",
        "line_code": "AL-2",
        "station": Station(120.0),
        "kind": JointKind.MONOLITHIC,
        "separates": "Ashfield compressor station",
        "installed_on": dt.date(2004, 9, 1),
    }
    kwargs.update(overrides)
    return IsolationJoint(**kwargs)  # type: ignore[arg-type]


def test_a_casing_survives_a_round_trip(register: Database) -> None:
    casings = CasingRepository(register)
    original = casing(length_m=32.0, carries="A19 dual carriageway")
    casings.add(original)
    assert casings.get("CS-12") == original


def test_a_casing_covers_a_stretch_rather_than_a_point() -> None:
    assert casing(length_m=32.0).extent.length_m == pytest.approx(32.0)


def test_a_casing_with_no_length_is_refused() -> None:
    from dropcell.errors import ValidationError

    with pytest.raises(ValidationError):
        casing(length_m=0.0)


def test_a_crossing_survives_a_round_trip(register: Database) -> None:
    crossings = CrossingRepository(register)
    crossings.add(crossing(bonded=True))
    stored = crossings.get("XG-4")
    assert stored.foreign_operator == "Vale Water"
    assert stored.bonded is True


def test_a_bond_survives_a_round_trip(register: Database) -> None:
    bonds = BondRepository(register)
    bonds.add(bond(critical=True))
    stored = bonds.get("BD-7")
    assert stored.kind is BondKind.RESISTIVE
    assert stored.resistor_ohm == pytest.approx(0.03)
    assert stored.critical is True


def test_a_direct_bond_stores_a_null_resistor(register: Database) -> None:
    bonds = BondRepository(register)
    bonds.add(bond(kind=BondKind.DIRECT, resistor_ohm=None))
    assert bonds.get("BD-7").resistor_ohm is None


def test_critical_bonds_can_be_picked_out(register: Database) -> None:
    bonds = BondRepository(register)
    bonds.add(bond())
    bonds.add(bond(code="BD-8", critical=True, station=Station(4000.0)))
    assert [item.code for item in bonds.critical_on("AL-2")] == ["BD-8"]


def test_a_joint_survives_a_round_trip(register: Database) -> None:
    joints = IsolationJointRepository(register)
    joints.add(joint(surge_protector_fitted=True))
    stored = joints.get("IJ-2")
    assert stored.kind is JointKind.MONOLITHIC
    assert stored.surge_protector_fitted is True


def test_everything_comes_back_in_stationing_order(register: Database) -> None:
    casings = CasingRepository(register)
    casings.add(casing(code="CS-2", station=Station(4000.0)))
    casings.add(casing())
    assert [item.code for item in casings.for_line("AL-2")] == ["CS-12", "CS-2"]


def test_nothing_can_hang_off_a_line_that_is_not_there(database: Database) -> None:
    with pytest.raises(ConflictError):
        CasingRepository(database).add(casing())
    with pytest.raises(ConflictError):
        CrossingRepository(database).add(crossing())


def test_deleting_a_line_takes_all_four_with_it(register: Database) -> None:
    CasingRepository(register).add(casing())
    CrossingRepository(register).add(crossing())
    BondRepository(register).add(bond())
    IsolationJointRepository(register).add(joint())
    LineRepository(register).delete("AL-2")
    assert CasingRepository(register).count() == 0
    assert CrossingRepository(register).count() == 0
    assert BondRepository(register).count() == 0
    assert IsolationJointRepository(register).count() == 0


def test_each_repository_names_its_own_record_kind(register: Database) -> None:
    with pytest.raises(NotFoundError) as caught:
        BondRepository(register).get("BD-9")
    assert "bond" in caught.value.message
