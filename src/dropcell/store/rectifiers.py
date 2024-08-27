"""Reading and writing rectifiers, their groundbeds and their check sheets.

The three tables belong together because the questions asked of them cross all
three. How much has this bed passed is a sum over the checks of the unit that
feeds it. Whether a unit has headroom is its checks against its own nameplate.
Neither can be answered from one table.

Checks are unique on the unit and the date for the same reason readings are
unique on the lead and the date. Two check sheets for the same unit on the same
day means somebody transcribed the wrong tag, and averaging them would hide it.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterable

from dropcell.model.enums import AnodeMaterial, GroundbedKind
from dropcell.model.groundbed import Groundbed
from dropcell.model.ids import normalise_code
from dropcell.model.rectifier import Rectifier, RectifierCheck
from dropcell.stationing import Station
from dropcell.store.base import Repository
from dropcell.store.database import Database

GROUNDBED_COLUMNS = (
    "code, kind, material, anode_count, anode_mass_kg, installed_on, "
    "design_current_a, utilisation, description"
)

RECTIFIER_COLUMNS = (
    "tag, line_code, station_m, groundbed_code, rated_voltage_v, rated_current_a, "
    "coarse_taps, fine_taps, installed_on, interrupter_fitted, description"
)

CHECK_COLUMNS = (
    "rectifier_tag, checked_on, output_voltage_v, output_current_a, coarse_tap, "
    "fine_tap, hour_meter, technician, comment"
)


def row_to_groundbed(row: sqlite3.Row) -> Groundbed:
    """Rebuild a groundbed from a register row."""
    return Groundbed(
        code=str(row["code"]),
        kind=GroundbedKind(row["kind"]),
        material=AnodeMaterial(row["material"]),
        anode_count=int(row["anode_count"]),
        anode_mass_kg=float(row["anode_mass_kg"]),
        installed_on=dt.date.fromisoformat(str(row["installed_on"])),
        design_current_a=float(row["design_current_a"]),
        utilisation=float(row["utilisation"]),
        description=str(row["description"]),
    )


def row_to_rectifier(row: sqlite3.Row) -> Rectifier:
    """Rebuild a rectifier from a register row."""
    return Rectifier(
        tag=str(row["tag"]),
        line_code=str(row["line_code"]),
        station=Station(float(row["station_m"])),
        groundbed_code=str(row["groundbed_code"]),
        rated_voltage_v=float(row["rated_voltage_v"]),
        rated_current_a=float(row["rated_current_a"]),
        coarse_taps=int(row["coarse_taps"]),
        fine_taps=int(row["fine_taps"]),
        installed_on=dt.date.fromisoformat(str(row["installed_on"])),
        interrupter_fitted=bool(row["interrupter_fitted"]),
        description=str(row["description"]),
    )


def row_to_check(row: sqlite3.Row) -> RectifierCheck:
    """Rebuild a check from a register row."""
    return RectifierCheck(
        rectifier_tag=str(row["rectifier_tag"]),
        checked_on=dt.date.fromisoformat(str(row["checked_on"])),
        output_voltage_v=float(row["output_voltage_v"]),
        output_current_a=float(row["output_current_a"]),
        coarse_tap=int(row["coarse_tap"]),
        fine_tap=int(row["fine_tap"]),
        hour_meter=None if row["hour_meter"] is None else float(row["hour_meter"]),
        technician=str(row["technician"]),
        comment=str(row["comment"]),
    )


class GroundbedRepository(Repository[Groundbed]):
    """Every anode bed in the register."""

    table = "groundbed"
    columns = GROUNDBED_COLUMNS
    noun = "groundbed"

    def to_record(self, row: sqlite3.Row) -> Groundbed:
        """Rebuild a groundbed from a register row."""
        return row_to_groundbed(row)

    def add(self, bed: Groundbed) -> Groundbed:
        """Insert a bed."""
        self.database.execute(
            f"INSERT INTO groundbed ({GROUNDBED_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                bed.code,
                str(bed.kind),
                str(bed.material),
                bed.anode_count,
                bed.anode_mass_kg,
                bed.installed_on.isoformat(),
                bed.design_current_a,
                bed.utilisation,
                bed.description,
            ),
        )
        return bed


class RectifierRepository(Repository[Rectifier]):
    """Every impressed current unit in the register."""

    table = "rectifier"
    columns = RECTIFIER_COLUMNS
    noun = "rectifier"
    key_column = "tag"
    order_by = "line_code, station_m"

    def to_record(self, row: sqlite3.Row) -> Rectifier:
        """Rebuild a rectifier from a register row."""
        return row_to_rectifier(row)

    @property
    def code_kind(self) -> str:
        """A rectifier is looked up by tag rather than by code."""
        return "rectifier tag"

    def add(self, unit: Rectifier) -> Rectifier:
        """Insert a unit."""
        self.database.execute(
            f"INSERT INTO rectifier ({RECTIFIER_COLUMNS})"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                unit.tag,
                unit.line_code,
                unit.station.metres,
                unit.groundbed_code,
                unit.rated_voltage_v,
                unit.rated_current_a,
                unit.coarse_taps,
                unit.fine_taps,
                unit.installed_on.isoformat(),
                int(unit.interrupter_fitted),
                unit.description,
            ),
        )
        return unit

    def for_line(self, line_code: str) -> list[Rectifier]:
        """Every unit on one line, in stationing order."""
        rows = self.database.query(
            f"SELECT {RECTIFIER_COLUMNS} FROM rectifier WHERE line_code = ? ORDER BY station_m",
            (normalise_code(line_code, kind="line code"),),
        )
        return [row_to_rectifier(row) for row in rows]

    def on_groundbed(self, groundbed_code: str) -> list[Rectifier]:
        """Every unit feeding one bed."""
        rows = self.database.query(
            f"SELECT {RECTIFIER_COLUMNS} FROM rectifier WHERE groundbed_code = ? ORDER BY tag",
            (normalise_code(groundbed_code, kind="groundbed code"),),
        )
        return [row_to_rectifier(row) for row in rows]


class RectifierCheckRepository:
    """Every visit to every unit."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, check: RectifierCheck) -> RectifierCheck:
        """Insert one check."""
        self.database.execute(
            f"INSERT INTO rectifier_check ({CHECK_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                check.rectifier_tag,
                check.checked_on.isoformat(),
                check.output_voltage_v,
                check.output_current_a,
                check.coarse_tap,
                check.fine_tap,
                check.hour_meter,
                check.technician,
                check.comment,
            ),
        )
        return check

    def add_many(self, checks: Iterable[RectifierCheck]) -> int:
        """Insert a batch and report how many landed."""
        rows = [
            (
                check.rectifier_tag,
                check.checked_on.isoformat(),
                check.output_voltage_v,
                check.output_current_a,
                check.coarse_tap,
                check.fine_tap,
                check.hour_meter,
                check.technician,
                check.comment,
            )
            for check in checks
        ]
        if not rows:
            return 0
        self.database.executemany(
            f"INSERT INTO rectifier_check ({CHECK_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        return len(rows)

    def for_unit(
        self,
        tag: str,
        *,
        since: dt.date | None = None,
        until: dt.date | None = None,
    ) -> list[RectifierCheck]:
        """Checks on one unit, oldest first."""
        sql = f"SELECT {CHECK_COLUMNS} FROM rectifier_check WHERE rectifier_tag = ?"
        params: list[object] = [normalise_code(tag, kind="rectifier tag")]
        if since is not None:
            sql += " AND checked_on >= ?"
            params.append(since.isoformat())
        if until is not None:
            sql += " AND checked_on <= ?"
            params.append(until.isoformat())
        sql += " ORDER BY checked_on"
        return [row_to_check(row) for row in self.database.query(sql, params)]

    def latest(self, tag: str) -> RectifierCheck | None:
        """The most recent check on one unit."""
        row = self.database.query_one(
            f"SELECT {CHECK_COLUMNS} FROM rectifier_check WHERE rectifier_tag = ?"
            " ORDER BY checked_on DESC LIMIT 1",
            (normalise_code(tag, kind="rectifier tag"),),
        )
        return None if row is None else row_to_check(row)

    def visit_dates(self, tag: str) -> list[dt.date]:
        """When a unit was visited, which is what the schedule runs off."""
        return [check.checked_on for check in self.for_unit(tag)]

    def count(self) -> int:
        """How many checks the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM rectifier_check") or 0)
