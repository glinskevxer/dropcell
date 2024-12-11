"""Reading and writing the plant that is not pipe, post or rectifier.

Casings, crossings, bonds and isolating joints all hang off a line at a station
and all get deleted with it. They are gathered in one module because they are
the same shape and because nothing useful is gained by four files that differ
in a table name.

None of these carry their test results. A casing test and an isolation test are
readings, they belong with the readings, and mixing a record that changes twice
in fifty years with one that changes twice a year in the same table is how a
schema stops being able to answer either question.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from dropcell.interference.bonds import Bond, BondKind
from dropcell.interference.foreign import Crossing
from dropcell.interference.isolation import IsolationJoint, JointKind
from dropcell.model.casing import Casing
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station
from dropcell.store.base import Repository

CASING_COLUMNS = "code, line_code, station_m, length_m, carries, installed_on, description"
CROSSING_COLUMNS = (
    "code, line_code, station_m, foreign_operator, foreign_structure, bonded, description"
)
BOND_COLUMNS = (
    "code, line_code, station_m, kind, to_structure, installed_on, design_current_a, "
    "resistor_ohm, critical, description"
)
JOINT_COLUMNS = (
    "code, line_code, station_m, kind, separates, installed_on, "
    "surge_protector_fitted, description"
)


class _OnLine[T](Repository[T]):
    """Shared lookup for anything that hangs off a line at a station."""

    order_by = "line_code, station_m"

    def for_line(self, line_code: str) -> list[T]:
        """Everything of this kind on one line, in stationing order."""
        rows = self.database.query(
            f"SELECT {self.columns} FROM {self.table} WHERE line_code = ?"
            " ORDER BY station_m, code",
            (normalise_code(line_code, kind="line code"),),
        )
        return [self.to_record(row) for row in rows]


class CasingRepository(_OnLine[Casing]):
    """Every cased crossing."""

    table = "casing"
    columns = CASING_COLUMNS
    noun = "casing"

    def to_record(self, row: sqlite3.Row) -> Casing:
        """Rebuild a casing from a register row."""
        return Casing(
            code=str(row["code"]),
            line_code=str(row["line_code"]),
            station=Station(float(row["station_m"])),
            installed_on=dt.date.fromisoformat(str(row["installed_on"])),
            length_m=float(row["length_m"]),
            carries=str(row["carries"]),
            description=str(row["description"]),
        )

    def add(self, casing: Casing) -> Casing:
        """Insert a casing."""
        self.database.execute(
            f"INSERT INTO casing ({CASING_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                casing.code,
                casing.line_code,
                casing.station.metres,
                casing.length_m,
                casing.carries,
                casing.installed_on.isoformat(),
                casing.description,
            ),
        )
        return casing


class CrossingRepository(_OnLine[Crossing]):
    """Every foreign structure crossing."""

    table = "crossing"
    columns = CROSSING_COLUMNS
    noun = "crossing"

    def to_record(self, row: sqlite3.Row) -> Crossing:
        """Rebuild a crossing from a register row."""
        return Crossing(
            code=str(row["code"]),
            line_code=str(row["line_code"]),
            station=Station(float(row["station_m"])),
            foreign_operator=str(row["foreign_operator"]),
            foreign_structure=str(row["foreign_structure"]),
            bonded=bool(row["bonded"]),
            description=str(row["description"]),
        )

    def add(self, crossing: Crossing) -> Crossing:
        """Insert a crossing."""
        self.database.execute(
            f"INSERT INTO crossing ({CROSSING_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                crossing.code,
                crossing.line_code,
                crossing.station.metres,
                crossing.foreign_operator,
                crossing.foreign_structure,
                int(crossing.bonded),
                crossing.description,
            ),
        )
        return crossing


class BondRepository(_OnLine[Bond]):
    """Every bond."""

    table = "bond"
    columns = BOND_COLUMNS
    noun = "bond"

    def to_record(self, row: sqlite3.Row) -> Bond:
        """Rebuild a bond from a register row."""
        return Bond(
            code=str(row["code"]),
            line_code=str(row["line_code"]),
            station=Station(float(row["station_m"])),
            kind=BondKind(row["kind"]),
            to_structure=str(row["to_structure"]),
            installed_on=dt.date.fromisoformat(str(row["installed_on"])),
            design_current_a=float(row["design_current_a"]),
            resistor_ohm=(None if row["resistor_ohm"] is None else float(row["resistor_ohm"])),
            critical=bool(row["critical"]),
            description=str(row["description"]),
        )

    def add(self, bond: Bond) -> Bond:
        """Insert a bond."""
        self.database.execute(
            f"INSERT INTO bond ({BOND_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                bond.code,
                bond.line_code,
                bond.station.metres,
                str(bond.kind),
                bond.to_structure,
                bond.installed_on.isoformat(),
                bond.design_current_a,
                bond.resistor_ohm,
                int(bond.critical),
                bond.description,
            ),
        )
        return bond

    def critical_on(self, line_code: str) -> list[Bond]:
        """Only the bonds on one line whose loss takes protection with it."""
        return [bond for bond in self.for_line(line_code) if bond.critical]


class IsolationJointRepository(_OnLine[IsolationJoint]):
    """Every isolating joint."""

    table = "isolation_joint"
    columns = JOINT_COLUMNS
    noun = "joint"

    def to_record(self, row: sqlite3.Row) -> IsolationJoint:
        """Rebuild a joint from a register row."""
        return IsolationJoint(
            code=str(row["code"]),
            line_code=str(row["line_code"]),
            station=Station(float(row["station_m"])),
            kind=JointKind(row["kind"]),
            separates=str(row["separates"]),
            installed_on=dt.date.fromisoformat(str(row["installed_on"])),
            surge_protector_fitted=bool(row["surge_protector_fitted"]),
            description=str(row["description"]),
        )

    def add(self, joint: IsolationJoint) -> IsolationJoint:
        """Insert an isolating joint."""
        self.database.execute(
            f"INSERT INTO isolation_joint ({JOINT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                joint.code,
                joint.line_code,
                joint.station.metres,
                str(joint.kind),
                joint.separates,
                joint.installed_on.isoformat(),
                int(joint.surge_protector_fitted),
                joint.description,
            ),
        )
        return joint
