"""Keeping the interference tests rather than only their verdicts.

The verdicts are derived and are printed on demand. The readings are evidence
and have to be kept, because a crossing that was tested clear three years
running and shorted this year is a different problem from one that has been
shorted since anybody looked, and only the history tells the two apart.

One test per thing per day, for the same reason as everywhere else in this
register. Two casing tests on one crossing on one afternoon means somebody read
it twice and got different answers, which is worth stopping on.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any

from dropcell.interference.bonds import BondCheck
from dropcell.interference.casing import CasingTest
from dropcell.interference.foreign import SwingTest
from dropcell.interference.isolation import IsolationTest
from dropcell.model.casing import Casing
from dropcell.model.ids import normalise_code
from dropcell.store.database import Database


def _optional(value: Any) -> float | None:
    return None if value is None else float(value)


class TestHistory:
    """Every interference test ever taken."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add_casing_test(self, test: CasingTest) -> CasingTest:
        """Record one casing test."""
        self.database.execute(
            "INSERT INTO casing_test (casing_code, tested_on, pipe_on_mv, casing_on_mv,"
            " pipe_off_mv, casing_off_mv, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                test.casing_code,
                test.tested_on.isoformat(),
                test.pipe_on_mv,
                test.casing_on_mv,
                test.pipe_off_mv,
                test.casing_off_mv,
                test.remark,
            ),
        )
        return test

    def casing_tests(self, casing: Casing) -> list[CasingTest]:
        """Every test on one casing, oldest first.

        The casing record is taken rather than its code because a test carries
        where it was taken, and the only place that is known is the casing. An
        earlier version defaulted the line and the station when they were not
        supplied, which produced tests claiming to be on a line called AL-0 at
        station zero, and those went straight into a report.
        """
        rows = self.database.query(
            "SELECT casing_code, tested_on, pipe_on_mv, casing_on_mv, pipe_off_mv,"
            " casing_off_mv, remark FROM casing_test WHERE casing_code = ?"
            " ORDER BY tested_on",
            (casing.code,),
        )
        return [self._casing(row, casing) for row in rows]

    def _casing(self, row: sqlite3.Row, casing: Casing) -> CasingTest:
        return CasingTest(
            casing_code=str(row["casing_code"]),
            line_code=casing.line_code,
            station=casing.station,
            tested_on=dt.date.fromisoformat(str(row["tested_on"])),
            pipe_on_mv=float(row["pipe_on_mv"]),
            casing_on_mv=float(row["casing_on_mv"]),
            pipe_off_mv=_optional(row["pipe_off_mv"]),
            casing_off_mv=_optional(row["casing_off_mv"]),
            remark=str(row["remark"]),
        )

    def add_swing_test(self, test: SwingTest) -> SwingTest:
        """Record one swing test at a crossing."""
        self.database.execute(
            "INSERT INTO swing_test (crossing_code, tested_on, foreign_with_ours_on_mv,"
            " foreign_with_ours_off_mv, ours_on_mv, ours_off_mv,"
            " their_rectifier_interrupted, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                test.crossing_code,
                test.tested_on.isoformat(),
                test.foreign_with_ours_on_mv,
                test.foreign_with_ours_off_mv,
                test.ours_on_mv,
                test.ours_off_mv,
                int(test.their_rectifier_interrupted),
                test.remark,
            ),
        )
        return test

    def swing_tests(self, code: str) -> list[SwingTest]:
        """Every swing test at one crossing, oldest first."""
        rows = self.database.query(
            "SELECT crossing_code, tested_on, foreign_with_ours_on_mv,"
            " foreign_with_ours_off_mv, ours_on_mv, ours_off_mv,"
            " their_rectifier_interrupted, remark FROM swing_test"
            " WHERE crossing_code = ? ORDER BY tested_on",
            (normalise_code(code, kind="crossing code"),),
        )
        return [
            SwingTest(
                crossing_code=str(row["crossing_code"]),
                tested_on=dt.date.fromisoformat(str(row["tested_on"])),
                foreign_with_ours_on_mv=float(row["foreign_with_ours_on_mv"]),
                foreign_with_ours_off_mv=float(row["foreign_with_ours_off_mv"]),
                ours_on_mv=_optional(row["ours_on_mv"]),
                ours_off_mv=_optional(row["ours_off_mv"]),
                their_rectifier_interrupted=bool(row["their_rectifier_interrupted"]),
                remark=str(row["remark"]),
            )
            for row in rows
        ]

    def add_bond_check(self, check: BondCheck) -> BondCheck:
        """Record one bond check."""
        self.database.execute(
            "INSERT INTO bond_check (bond_code, checked_on, current_a,"
            " reversed_polarity, remark) VALUES (?, ?, ?, ?, ?)",
            (
                check.bond_code,
                check.checked_on.isoformat(),
                check.current_a,
                int(check.reversed_polarity),
                check.remark,
            ),
        )
        return check

    def bond_checks(self, code: str) -> list[BondCheck]:
        """Every check on one bond, oldest first."""
        rows = self.database.query(
            "SELECT bond_code, checked_on, current_a, reversed_polarity, remark"
            " FROM bond_check WHERE bond_code = ? ORDER BY checked_on",
            (normalise_code(code, kind="bond code"),),
        )
        return [
            BondCheck(
                bond_code=str(row["bond_code"]),
                checked_on=dt.date.fromisoformat(str(row["checked_on"])),
                current_a=float(row["current_a"]),
                reversed_polarity=bool(row["reversed_polarity"]),
                remark=str(row["remark"]),
            )
            for row in rows
        ]

    def add_isolation_test(self, test: IsolationTest) -> IsolationTest:
        """Record one isolation test."""
        self.database.execute(
            "INSERT INTO isolation_test (joint_code, tested_on, our_side_mv,"
            " other_side_mv, surge_protector_removed, technician, remark)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                test.joint_code,
                test.tested_on.isoformat(),
                test.our_side_mv,
                test.other_side_mv,
                int(test.surge_protector_removed),
                test.technician,
                test.remark,
            ),
        )
        return test

    def isolation_tests(self, code: str) -> list[IsolationTest]:
        """Every test on one joint, oldest first."""
        rows = self.database.query(
            "SELECT joint_code, tested_on, our_side_mv, other_side_mv,"
            " surge_protector_removed, technician, remark FROM isolation_test"
            " WHERE joint_code = ? ORDER BY tested_on",
            (normalise_code(code, kind="joint code"),),
        )
        return [
            IsolationTest(
                joint_code=str(row["joint_code"]),
                tested_on=dt.date.fromisoformat(str(row["tested_on"])),
                our_side_mv=float(row["our_side_mv"]),
                other_side_mv=float(row["other_side_mv"]),
                surge_protector_removed=bool(row["surge_protector_removed"]),
                technician=str(row["technician"]),
                remark=str(row["remark"]),
            )
            for row in rows
        ]

    def visit_dates(self, table: str, key_column: str, code: str) -> list[dt.date]:
        """When something was last visited, for the monitoring schedule."""
        column = "tested_on" if table != "bond_check" else "checked_on"
        rows = self.database.query(
            f"SELECT {column} AS when_on FROM {table} WHERE {key_column} = ? ORDER BY {column}",
            (code,),
        )
        return [dt.date.fromisoformat(str(row["when_on"])) for row in rows]

    def latest_casing_test(self, casing: Casing) -> CasingTest | None:
        """The most recent test on one casing."""
        found = self.casing_tests(casing)
        return found[-1] if found else None

    def latest_swing_test(self, code: str) -> SwingTest | None:
        """The most recent swing test at one crossing."""
        found = self.swing_tests(code)
        return found[-1] if found else None

    def latest_bond_check(self, code: str) -> BondCheck | None:
        """The most recent check on one bond."""
        found = self.bond_checks(code)
        return found[-1] if found else None

    def latest_isolation_test(self, code: str) -> IsolationTest | None:
        """The most recent test on one joint."""
        found = self.isolation_tests(code)
        return found[-1] if found else None
