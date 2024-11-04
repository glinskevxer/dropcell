"""Reading and writing coupons and their readings.

A coupon hangs off a test post rather than off a line, because that is how it
is wired and how a crew finds it. Removing the post removes the coupon, which
is right: the wires ran to that terminal board and nowhere else.

One reading per coupon per day, for the same reason there is one reading per
lead per day. A coupon read twice in a morning is a coupon somebody read on the
way out and again on the way back, and the two numbers disagreeing is the
finding rather than something to average away.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterable

from dropcell.model.coupon import Coupon, CouponOrientation, CouponReading
from dropcell.model.ids import normalise_code
from dropcell.store.base import Repository
from dropcell.store.database import Database

COUPON_COLUMNS = (
    "code, test_point_code, area_m2, shunt_ohm, installed_on, orientation, depth_m, description"
)

COUPON_READING_COLUMNS = (
    "coupon_code, taken_on, on_mv, disconnected_mv, dc_shunt_mv, ac_shunt_mv, "
    "ac_voltage_v, technician, comment"
)


def row_to_coupon(row: sqlite3.Row) -> Coupon:
    """Rebuild a coupon from a register row."""
    return Coupon(
        code=str(row["code"]),
        test_point_code=str(row["test_point_code"]),
        area_m2=float(row["area_m2"]),
        shunt_ohm=float(row["shunt_ohm"]),
        installed_on=dt.date.fromisoformat(str(row["installed_on"])),
        orientation=CouponOrientation(row["orientation"]),
        depth_m=float(row["depth_m"]),
        description=str(row["description"]),
    )


def row_to_coupon_reading(row: sqlite3.Row) -> CouponReading:
    """Rebuild a coupon reading from a register row."""
    return CouponReading(
        coupon_code=str(row["coupon_code"]),
        taken_on=dt.date.fromisoformat(str(row["taken_on"])),
        on_mv=float(row["on_mv"]),
        disconnected_mv=(
            None if row["disconnected_mv"] is None else float(row["disconnected_mv"])
        ),
        dc_shunt_mv=None if row["dc_shunt_mv"] is None else float(row["dc_shunt_mv"]),
        ac_shunt_mv=None if row["ac_shunt_mv"] is None else float(row["ac_shunt_mv"]),
        ac_voltage_v=None if row["ac_voltage_v"] is None else float(row["ac_voltage_v"]),
        technician=str(row["technician"]),
        comment=str(row["comment"]),
    )


class CouponRepository(Repository[Coupon]):
    """Every coupon in the register."""

    table = "coupon"
    columns = COUPON_COLUMNS
    noun = "coupon"
    order_by = "test_point_code, code"

    def to_record(self, row: sqlite3.Row) -> Coupon:
        """Rebuild a coupon from a register row."""
        return row_to_coupon(row)

    def add(self, coupon: Coupon) -> Coupon:
        """Insert a coupon."""
        self.database.execute(
            f"INSERT INTO coupon ({COUPON_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                coupon.code,
                coupon.test_point_code,
                coupon.area_m2,
                coupon.shunt_ohm,
                coupon.installed_on.isoformat(),
                str(coupon.orientation),
                coupon.depth_m,
                coupon.description,
            ),
        )
        return coupon

    def for_post(self, test_point_code: str) -> list[Coupon]:
        """Every coupon wired to one post."""
        rows = self.database.query(
            f"SELECT {COUPON_COLUMNS} FROM coupon WHERE test_point_code = ? ORDER BY code",
            (normalise_code(test_point_code, kind="test point code"),),
        )
        return [row_to_coupon(row) for row in rows]

    def for_line(self, line_code: str) -> list[Coupon]:
        """Every coupon on one line, in stationing order."""
        rows = self.database.query(
            "SELECT c.code AS code, c.test_point_code AS test_point_code,"
            " c.area_m2 AS area_m2, c.shunt_ohm AS shunt_ohm,"
            " c.installed_on AS installed_on, c.orientation AS orientation,"
            " c.depth_m AS depth_m, c.description AS description"
            " FROM coupon c JOIN test_point t ON t.code = c.test_point_code"
            " WHERE t.line_code = ? ORDER BY t.station_m, c.code",
            (normalise_code(line_code, kind="line code"),),
        )
        return [row_to_coupon(row) for row in rows]


class CouponReadingRepository:
    """Every coupon reading in the register."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, reading: CouponReading) -> CouponReading:
        """Insert one reading."""
        self.database.execute(
            f"INSERT INTO coupon_reading ({COUPON_READING_COLUMNS})"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reading.coupon_code,
                reading.taken_on.isoformat(),
                reading.on_mv,
                reading.disconnected_mv,
                reading.dc_shunt_mv,
                reading.ac_shunt_mv,
                reading.ac_voltage_v,
                reading.technician,
                reading.comment,
            ),
        )
        return reading

    def add_many(self, readings: Iterable[CouponReading]) -> int:
        """Insert a batch and report how many landed."""
        count = 0
        for reading in readings:
            self.add(reading)
            count += 1
        return count

    def for_coupon(self, code: str) -> list[CouponReading]:
        """Readings on one coupon, oldest first."""
        rows = self.database.query(
            f"SELECT {COUPON_READING_COLUMNS} FROM coupon_reading"
            " WHERE coupon_code = ? ORDER BY taken_on",
            (normalise_code(code, kind="coupon code"),),
        )
        return [row_to_coupon_reading(row) for row in rows]

    def latest(self, code: str) -> CouponReading | None:
        """The most recent reading on one coupon."""
        row = self.database.query_one(
            f"SELECT {COUPON_READING_COLUMNS} FROM coupon_reading"
            " WHERE coupon_code = ? ORDER BY taken_on DESC LIMIT 1",
            (normalise_code(code, kind="coupon code"),),
        )
        return None if row is None else row_to_coupon_reading(row)

    def count(self) -> int:
        """How many coupon readings the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM coupon_reading") or 0)
