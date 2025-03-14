"""The interference page, which is four different problems on one sheet.

Casings, crossings, bonds and isolating joints have nothing in common
mechanically and everything in common operationally: they are the places where
our current and somebody else's meet, they are all tested by comparing two
potentials, and they all fail in a way that leaves every test post reading
perfectly.

They go on one page because that is how they are worked. A crew doing an
interference round does all four in a morning, and a report that splits them
across four pages produces four rounds.

Anything never tested is on the page with the rest. A joint that has been in the
ground twenty years and has never been read is not a clean joint, and leaving it
off a page headed with the things that were tested is how it stays that way.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.interference.bonds import Bond, BondCheck, BondHealth, assess_bond
from dropcell.interference.casing import CasingTest, classify_casing
from dropcell.interference.foreign import SwingTest, classify_swing
from dropcell.interference.isolation import IsolationJoint, IsolationTest, classify_isolation
from dropcell.model.casing import Casing
from dropcell.model.line import Line
from dropcell.report.table import Column, Table
from dropcell.stationing import Station

PLANT_COLUMNS = (
    Column("code", "Code"),
    Column("kind", "Kind", width=10),
    Column("station", "Station", align="right"),
    Column("tested", "Last test"),
    Column("verdict", "Verdict", width=18),
    Column("due", "Deal with by"),
    Column("note", "Note", width=42),
)


@dataclass(frozen=True)
class PlantRow:
    """One piece of plant, its last test and what that test said."""

    code: str
    kind: str
    station: Station
    tested_on: dt.date | None
    verdict: str
    due_by: dt.date | None
    note: str

    @property
    def never_tested(self) -> bool:
        """Whether anybody has read it at all."""
        return self.tested_on is None

    @property
    def needs_work(self) -> bool:
        """Whether it is on somebody's list."""
        return self.never_tested or self.verdict not in {
            "clear",
            "none",
            "isolating",
            "healthy",
        }

    @property
    def sort_key(self) -> tuple[int, int, str]:
        """Never tested first, then anything that needs work, then by code."""
        return (
            0 if self.never_tested else (1 if self.needs_work else 2),
            0,
            self.code,
        )


def casing_row(casing: Casing, test: CasingTest | None) -> PlantRow:
    """One casing, read or not."""
    if test is None:
        return PlantRow(
            code=casing.code,
            kind="casing",
            station=casing.station,
            tested_on=None,
            verdict="never tested",
            due_by=None,
            note=f"{casing.length_m:.0f} m under {casing.carries or 'something'}",
        )
    verdict = classify_casing(test)
    return PlantRow(
        code=casing.code,
        kind="casing",
        station=casing.station,
        tested_on=test.tested_on,
        verdict=str(verdict.status),
        due_by=verdict.due_by,
        note=verdict.reason,
    )


def crossing_row(
    code: str, station: Station, operator: str, test: SwingTest | None
) -> PlantRow:
    """One crossing, read or not."""
    if test is None:
        return PlantRow(
            code=code,
            kind="crossing",
            station=station,
            tested_on=None,
            verdict="never tested",
            due_by=None,
            note=f"crosses {operator}",
        )
    verdict = classify_swing(test)
    return PlantRow(
        code=code,
        kind="crossing",
        station=station,
        tested_on=test.tested_on,
        verdict=str(verdict.verdict),
        due_by=None,
        note=verdict.reason,
    )


def bond_row(bond: Bond, check: BondCheck | None) -> PlantRow:
    """One bond, read or not."""
    if check is None:
        return PlantRow(
            code=bond.code,
            kind="bond",
            station=bond.station,
            tested_on=None,
            verdict="never tested",
            due_by=None,
            note=f"to {bond.to_structure}",
        )
    health = assess_bond(bond, check)
    note = f"{check.current_a:.3f} A against a design of {bond.design_current_a:.3f} A"
    if bond.critical and health is not BondHealth.HEALTHY:
        note = "protection depends on this bond. " + note
    return PlantRow(
        code=bond.code,
        kind="bond",
        station=bond.station,
        tested_on=check.checked_on,
        verdict=str(health),
        due_by=None,
        note=note,
    )


def joint_row(joint: IsolationJoint, test: IsolationTest | None) -> PlantRow:
    """One isolating joint, read or not."""
    if test is None:
        return PlantRow(
            code=joint.code,
            kind="joint",
            station=joint.station,
            tested_on=None,
            verdict="never tested",
            due_by=None,
            note=f"separates {joint.separates}",
        )
    verdict = classify_isolation(test, joint)
    return PlantRow(
        code=joint.code,
        kind="joint",
        station=joint.station,
        tested_on=test.tested_on,
        verdict=str(verdict.status),
        due_by=verdict.due_by,
        note=verdict.reason,
    )


def render_interference(line: Line, rows: list[PlantRow], *, as_of: dt.date) -> str:
    """The whole page."""
    table = Table(
        columns=PLANT_COLUMNS,
        title=f"Interference, {line.code} {line.name}",
        empty_note="nothing on this line but pipe, posts and rectifiers",
    )
    for row in sorted(rows, key=lambda item: item.sort_key):
        table.add(
            code=row.code,
            kind=row.kind,
            station=line.format_station(row.station),
            tested=row.tested_on.isoformat() if row.tested_on else "never",
            verdict=row.verdict,
            due=row.due_by.isoformat() if row.due_by else "",
            note=row.note,
        )
    never = sum(1 for row in rows if row.never_tested)
    work = sum(1 for row in rows if row.needs_work and not row.never_tested)
    return "\n".join(
        [
            f"as at {as_of.isoformat()}",
            "",
            table.render(),
            "",
            f"{len(rows)} pieces of plant, {never} never tested, {work} needing work",
        ]
    )
