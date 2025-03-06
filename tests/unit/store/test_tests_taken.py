from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError
from dropcell.interference.bonds import Bond, BondCheck, BondKind
from dropcell.interference.casing import CasingTest
from dropcell.interference.foreign import Crossing, SwingTest
from dropcell.interference.isolation import IsolationJoint, IsolationTest, JointKind
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
from dropcell.store.tests_taken import TestHistory

TESTED = dt.date(2025, 3, 14)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    CasingRepository(database).add(
        Casing(
            code="CS-12",
            line_code="AL-2",
            station=Station(1245.5),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    CrossingRepository(database).add(
        Crossing(
            code="XG-4",
            line_code="AL-2",
            station=Station(2400.0),
            foreign_operator="Vale Water",
            foreign_structure="18 inch main",
        )
    )
    BondRepository(database).add(
        Bond(
            code="BD-7",
            line_code="AL-2",
            station=Station(2400.0),
            kind=BondKind.DIRECT,
            to_structure="Vale Water main",
            installed_on=dt.date(2011, 4, 2),
            design_current_a=2.0,
        )
    )
    IsolationJointRepository(database).add(
        IsolationJoint(
            code="IJ-2",
            line_code="AL-2",
            station=Station(120.0),
            kind=JointKind.MONOLITHIC,
            separates="compressor station",
            installed_on=dt.date(2004, 9, 1),
        )
    )
    return database


def casing_test(**overrides: object) -> CasingTest:
    kwargs: dict[str, object] = {
        "casing_code": "CS-12",
        "line_code": "AL-2",
        "station": Station(1245.5),
        "tested_on": TESTED,
        "pipe_on_mv": -1120.0,
        "casing_on_mv": -560.0,
    }
    kwargs.update(overrides)
    return CasingTest(**kwargs)  # type: ignore[arg-type]


def test_a_casing_test_survives_a_round_trip(register: Database) -> None:
    history = TestHistory(register)
    history.add_casing_test(casing_test(pipe_off_mv=-905.0, casing_off_mv=-540.0))
    stored = history.casing_tests(CasingRepository(register).get("CS-12"))
    assert len(stored) == 1
    assert stored[0].pipe_off_mv == pytest.approx(-905.0)
    assert stored[0].separation_mv == pytest.approx(365.0)


def test_a_second_casing_test_on_one_day_is_refused(register: Database) -> None:
    history = TestHistory(register)
    history.add_casing_test(casing_test())
    with pytest.raises(ConflictError):
        history.add_casing_test(casing_test(casing_on_mv=-600.0))


def test_a_casing_test_against_nothing_is_refused(database: Database) -> None:
    with pytest.raises(ConflictError):
        TestHistory(database).add_casing_test(casing_test())


def test_casing_tests_come_back_oldest_first(register: Database) -> None:
    history = TestHistory(register)
    history.add_casing_test(casing_test())
    history.add_casing_test(casing_test(tested_on=dt.date(2023, 3, 14)))
    casing = CasingRepository(register).get("CS-12")
    dates = [item.tested_on for item in history.casing_tests(casing)]
    assert dates == sorted(dates)


def test_a_swing_test_survives_a_round_trip(register: Database) -> None:
    history = TestHistory(register)
    history.add_swing_test(
        SwingTest(
            crossing_code="XG-4",
            tested_on=TESTED,
            foreign_with_ours_on_mv=-700.0,
            foreign_with_ours_off_mv=-760.0,
            ours_on_mv=-1120.0,
            ours_off_mv=-905.0,
            their_rectifier_interrupted=True,
        )
    )
    stored = history.swing_tests("XG-4")[0]
    assert stored.foreign_swing_mv == pytest.approx(60.0)
    assert stored.their_rectifier_interrupted is True
    assert stored.our_swing_mv == pytest.approx(-215.0)


def test_a_bond_check_survives_a_round_trip(register: Database) -> None:
    history = TestHistory(register)
    history.add_bond_check(BondCheck(bond_code="BD-7", checked_on=TESTED, current_a=1.9))
    stored = history.bond_checks("BD-7")[0]
    assert stored.current_a == pytest.approx(1.9)
    assert not stored.is_open


def test_an_isolation_test_survives_a_round_trip(register: Database) -> None:
    history = TestHistory(register)
    history.add_isolation_test(
        IsolationTest(
            joint_code="IJ-2",
            tested_on=TESTED,
            our_side_mv=-1120.0,
            other_side_mv=-420.0,
            technician="R Ellis",
        )
    )
    stored = history.isolation_tests("IJ-2")[0]
    assert stored.separation_mv == pytest.approx(700.0)
    assert stored.technician == "R Ellis"


def test_the_visit_dates_are_what_the_schedule_reads(register: Database) -> None:
    history = TestHistory(register)
    history.add_casing_test(casing_test())
    history.add_casing_test(casing_test(tested_on=dt.date(2024, 3, 14)))
    assert history.visit_dates("casing_test", "casing_code", "CS-12") == [
        dt.date(2024, 3, 14),
        dt.date(2025, 3, 14),
    ]


def test_bond_visit_dates_read_the_other_column(register: Database) -> None:
    history = TestHistory(register)
    history.add_bond_check(BondCheck(bond_code="BD-7", checked_on=TESTED, current_a=1.9))
    assert history.visit_dates("bond_check", "bond_code", "BD-7") == [TESTED]


def test_deleting_a_line_takes_every_test_with_it(register: Database) -> None:
    history = TestHistory(register)
    history.add_casing_test(casing_test())
    history.add_bond_check(BondCheck(bond_code="BD-7", checked_on=TESTED, current_a=1.9))
    casing = CasingRepository(register).get("CS-12")
    LineRepository(register).delete("AL-2")
    assert history.casing_tests(casing) == []
    assert history.bond_checks("BD-7") == []
