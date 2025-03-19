from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.schedule import (
    bond_histories,
    casing_histories,
    joint_histories,
    line_histories,
    post_histories,
    rectifier_histories,
)
from dropcell.interference.bonds import Bond, BondCheck, BondKind
from dropcell.interference.casing import CasingTest
from dropcell.interference.isolation import IsolationJoint, IsolationTest, JointKind
from dropcell.model.casing import Casing
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.testpoint import TestPoint
from dropcell.schedule.policy import STANDARD_POLICY, AssetKind
from dropcell.schedule.register import build_register
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.interference import (
    BondRepository,
    CasingRepository,
    IsolationJointRepository,
)
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.testpoints import TestPointRepository
from dropcell.store.tests_taken import TestHistory

TODAY = dt.date(2025, 3, 14)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    TestPointRepository(database).add(
        TestPoint(
            code="TP-1",
            line_code="AL-2",
            station=Station(100.0),
            leads=frozenset({LeadKind.PIPE, LeadKind.CASING}),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    CasingRepository(database).add(
        Casing(
            code="CS-12",
            line_code="AL-2",
            station=Station(1245.5),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    BondRepository(database).add(
        Bond(
            code="BD-7",
            line_code="AL-2",
            station=Station(2400.0),
            kind=BondKind.DIRECT,
            to_structure="main",
            installed_on=dt.date(2011, 4, 2),
            design_current_a=2.0,
            critical=True,
        )
    )
    BondRepository(database).add(
        Bond(
            code="BD-8",
            line_code="AL-2",
            station=Station(4000.0),
            kind=BondKind.DIRECT,
            to_structure="main",
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
            separates="station",
            installed_on=dt.date(2004, 9, 1),
        )
    )
    return database


def test_a_post_history_reads_the_pipe_lead_only(register: Database) -> None:
    readings = ReadingRepository(register)
    readings.add(
        Reading(test_point_code="TP-1", lead=LeadKind.CASING, taken_on=TODAY, on_mv=-560.0)
    )
    assert post_histories(register, "AL-2")[0].visits == ()
    readings.add(
        Reading(test_point_code="TP-1", lead=LeadKind.PIPE, taken_on=TODAY, on_mv=-1120.0)
    )
    assert post_histories(register, "AL-2")[0].visits == (TODAY,)


def test_a_casing_history_comes_off_its_tests(register: Database) -> None:
    assert casing_histories(register, "AL-2")[0].visits == ()
    TestHistory(register).add_casing_test(
        CasingTest(
            casing_code="CS-12",
            line_code="AL-2",
            station=Station(1245.5),
            tested_on=TODAY,
            pipe_on_mv=-1120.0,
            casing_on_mv=-560.0,
        )
    )
    history = casing_histories(register, "AL-2")[0]
    assert history.visits == (TODAY,)
    assert history.kind is AssetKind.CASING


def test_a_critical_bond_falls_under_the_rectifier_rule(register: Database) -> None:
    kinds = {item.code: item.kind for item in bond_histories(register, "AL-2")}
    assert kinds["BD-7"] is AssetKind.CRITICAL_BOND
    assert kinds["BD-8"] is AssetKind.ORDINARY_BOND


def test_a_bond_history_comes_off_its_checks(register: Database) -> None:
    TestHistory(register).add_bond_check(
        BondCheck(bond_code="BD-7", checked_on=TODAY, current_a=2.0)
    )
    by_code = {item.code: item for item in bond_histories(register, "AL-2")}
    assert by_code["BD-7"].visits == (TODAY,)
    assert by_code["BD-8"].visits == ()


def test_a_joint_history_comes_off_its_tests(register: Database) -> None:
    TestHistory(register).add_isolation_test(
        IsolationTest(
            joint_code="IJ-2",
            tested_on=TODAY,
            our_side_mv=-1120.0,
            other_side_mv=-420.0,
        )
    )
    history = joint_histories(register, "AL-2")[0]
    assert history.visits == (TODAY,)
    assert history.kind is AssetKind.ISOLATION_JOINT


def test_everything_on_the_line_is_on_the_register(register: Database) -> None:
    histories = line_histories(register, "AL-2")
    codes = {item.code for item in histories}
    assert codes == {"TP-1", "CS-12", "BD-7", "BD-8", "IJ-2"}


def test_the_ordinary_bond_is_not_covered_by_any_rule(register: Database) -> None:
    built = build_register(STANDARD_POLICY, line_histories(register, "AL-2"), as_of=TODAY)
    covered = {item.asset_code for item in built}
    assert "BD-7" in covered
    assert "BD-8" not in covered


def test_a_casing_never_tested_lands_on_the_register(register: Database) -> None:
    built = build_register(STANDARD_POLICY, line_histories(register, "AL-2"), as_of=TODAY)
    by_code = {item.asset_code: item for item in built}
    assert by_code["CS-12"].rule_key == "casing_annual"
    assert not by_code["CS-12"].ever_visited


def test_a_line_with_no_rectifiers_still_builds(register: Database) -> None:
    assert rectifier_histories(register, "AL-2") == []
