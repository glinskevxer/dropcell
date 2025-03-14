from __future__ import annotations

import datetime as dt

from dropcell.interference.bonds import Bond, BondCheck, BondKind
from dropcell.interference.casing import CasingTest
from dropcell.interference.foreign import SwingTest
from dropcell.interference.isolation import IsolationJoint, IsolationTest, JointKind
from dropcell.model.casing import Casing
from dropcell.model.line import Line
from dropcell.report.interference import (
    bond_row,
    casing_row,
    crossing_row,
    joint_row,
    render_interference,
)
from dropcell.stationing import Station

TESTED = dt.date(2025, 3, 14)


def casing() -> Casing:
    return Casing(
        code="CS-12",
        line_code="AL-2",
        station=Station(1245.5),
        installed_on=dt.date(1998, 5, 4),
        carries="the A19",
    )


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


def bond(**overrides: object) -> Bond:
    kwargs: dict[str, object] = {
        "code": "BD-7",
        "line_code": "AL-2",
        "station": Station(2400.0),
        "kind": BondKind.DIRECT,
        "to_structure": "Vale Water main",
        "installed_on": dt.date(2011, 4, 2),
        "design_current_a": 2.0,
    }
    kwargs.update(overrides)
    return Bond(**kwargs)  # type: ignore[arg-type]


def joint() -> IsolationJoint:
    return IsolationJoint(
        code="IJ-2",
        line_code="AL-2",
        station=Station(120.0),
        kind=JointKind.MONOLITHIC,
        separates="compressor station",
        installed_on=dt.date(2004, 9, 1),
    )


def test_a_casing_never_tested_says_so() -> None:
    row = casing_row(casing(), None)
    assert row.never_tested
    assert row.needs_work
    assert "the A19" in row.note


def test_a_clear_casing_needs_no_work() -> None:
    row = casing_row(casing(), casing_test())
    assert row.verdict == "clear"
    assert not row.needs_work
    assert row.due_by is None


def test_a_shorted_casing_carries_a_date() -> None:
    row = casing_row(casing(), casing_test(casing_on_mv=-1116.0))
    assert row.verdict == "metallic_short"
    assert row.needs_work
    assert row.due_by is not None


def test_a_crossing_with_no_interference_needs_no_work() -> None:
    test = SwingTest(
        crossing_code="XG-4",
        tested_on=TESTED,
        foreign_with_ours_on_mv=-755.0,
        foreign_with_ours_off_mv=-760.0,
    )
    row = crossing_row("XG-4", Station(2400.0), "Vale Water", test)
    assert row.verdict == "none"
    assert not row.needs_work


def test_a_crossing_we_are_harming_needs_work() -> None:
    test = SwingTest(
        crossing_code="XG-4",
        tested_on=TESTED,
        foreign_with_ours_on_mv=-700.0,
        foreign_with_ours_off_mv=-760.0,
    )
    row = crossing_row("XG-4", Station(2400.0), "Vale Water", test)
    assert row.verdict == "harming_foreign"
    assert row.needs_work


def test_a_crossing_never_tested_names_the_operator() -> None:
    row = crossing_row("XG-4", Station(2400.0), "Vale Water", None)
    assert "Vale Water" in row.note


def test_a_healthy_bond_needs_no_work() -> None:
    check = BondCheck(bond_code="BD-7", checked_on=TESTED, current_a=2.0)
    row = bond_row(bond(), check)
    assert row.verdict == "healthy"
    assert not row.needs_work


def test_an_open_critical_bond_says_protection_depends_on_it() -> None:
    check = BondCheck(bond_code="BD-7", checked_on=TESTED, current_a=0.0)
    row = bond_row(bond(critical=True), check)
    assert row.verdict == "open"
    assert "protection depends on this bond" in row.note


def test_an_open_ordinary_bond_does_not() -> None:
    check = BondCheck(bond_code="BD-7", checked_on=TESTED, current_a=0.0)
    assert "protection depends" not in bond_row(bond(), check).note


def test_an_isolating_joint_needs_no_work() -> None:
    test = IsolationTest(
        joint_code="IJ-2", tested_on=TESTED, our_side_mv=-1120.0, other_side_mv=-420.0
    )
    row = joint_row(joint(), test)
    assert row.verdict == "isolating"
    assert not row.needs_work


def test_a_shorted_joint_carries_a_date() -> None:
    test = IsolationTest(
        joint_code="IJ-2", tested_on=TESTED, our_side_mv=-1120.0, other_side_mv=-1112.0
    )
    row = joint_row(joint(), test)
    assert row.verdict == "shorted"
    assert row.due_by is not None


def test_the_page_puts_the_untested_first(line: Line) -> None:
    rows = [
        casing_row(casing(), casing_test()),
        joint_row(joint(), None),
    ]
    rendered = render_interference(line, rows, as_of=TESTED)
    assert rendered.index("IJ-2") < rendered.index("CS-12")


def test_the_page_counts_what_it_carries(line: Line) -> None:
    rows = [
        casing_row(casing(), casing_test(casing_on_mv=-1116.0)),
        joint_row(joint(), None),
    ]
    rendered = render_interference(line, rows, as_of=TESTED)
    assert "2 pieces of plant, 1 never tested, 1 needing work" in rendered


def test_an_empty_page_says_so(line: Line) -> None:
    rendered = render_interference(line, [], as_of=TESTED)
    assert "nothing on this line but pipe, posts and rectifiers" in rendered


def test_the_page_prints_stations_in_the_line_convention(line: Line) -> None:
    rendered = render_interference(line, [casing_row(casing(), None)], as_of=TESTED)
    assert "40+86.29" in rendered
