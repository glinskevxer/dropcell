"""Loading coupon readings, which are the fussiest file to get right.

A coupon row carries a potential, two shunt drops and an AC voltage, and three
of those four are optional because different crews wire different meters up. A
row with nothing but a connected potential on it is a coupon read as though it
were a test post, which is a waste of a coupon and worth saying out loud.

The shunt drops are millivolts and the AC voltage is volts, on the same row.
That is not a design choice anybody made, it is what the instruments read, and
the profile carries the distinction so nothing has to remember it downstream.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.ingest.annual import SkippedRow
from dropcell.ingest.profiles import COUPON_PROFILE
from dropcell.ingest.reader import ReadResult, read_text
from dropcell.model.coupon import CouponReading
from dropcell.model.ids import normalise_code
from dropcell.store.coupons import CouponReadingRepository, CouponRepository
from dropcell.store.database import Database
from dropcell.store.imports import ImportLedger, ImportRun


@dataclass(frozen=True)
class CouponImport:
    """A coupon file, read and landed."""

    run: ImportRun
    written: int
    skipped: tuple[SkippedRow, ...]
    quarantined: int
    thin: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        """Whether every row landed."""
        return not self.skipped and self.quarantined == 0

    def reasons(self) -> tuple[str, ...]:
        """One line per row that did not land."""
        return tuple(
            f"row {item.row_number}: {item.reason}"
            + (f" ({item.detail})" if item.detail else "")
            for item in self.skipped
        )


def import_coupon_readings(
    database: Database,
    text: str,
    *,
    now: dt.datetime,
    source: str = "",
) -> CouponImport:
    """Load a coupon file, refusing a file that has been loaded before."""
    result = read_text(text, COUPON_PROFILE, source=source)
    return land_coupon_readings(database, result, now=now)


def land_coupon_readings(
    database: Database,
    result: ReadResult,
    *,
    now: dt.datetime,
) -> CouponImport:
    """Write an already read coupon file into the register."""
    ledger = ImportLedger(database)
    coupons = CouponRepository(database)
    readings = CouponReadingRepository(database)
    known: dict[str, bool] = {}
    seen: set[tuple[str, dt.date]] = set()
    to_write: list[CouponReading] = []
    skipped: list[SkippedRow] = []
    thin: list[str] = []
    for offset, row in enumerate(result.rows, start=2):
        code = normalise_code(str(row["coupon_code"]), kind="coupon code")
        if code not in known:
            known[code] = coupons.exists(code)
        if not known[code]:
            skipped.append(SkippedRow(offset, "no coupon with that code", code))
            continue
        taken_on = row["taken_on"]
        if (code, taken_on) in seen:
            skipped.append(
                SkippedRow(offset, "the file reads this coupon twice on one day", code)
            )
            continue
        if any(item.taken_on == taken_on for item in readings.for_coupon(code)):
            skipped.append(SkippedRow(offset, "already in the register", code))
            continue
        seen.add((code, taken_on))
        reading = CouponReading(
            coupon_code=code,
            taken_on=taken_on,
            on_mv=float(row["on_mv"]),
            disconnected_mv=row.get("disconnected_mv"),
            dc_shunt_mv=row.get("dc_shunt_mv"),
            ac_shunt_mv=row.get("ac_shunt_mv"),
            ac_voltage_v=row.get("ac_voltage_v"),
            technician=str(row.get("technician") or ""),
            comment=str(row.get("comment") or ""),
        )
        if (
            reading.disconnected_mv is None
            and reading.dc_shunt_mv is None
            and reading.ac_shunt_mv is None
        ):
            thin.append(f"{code} on {taken_on.isoformat()}")
        to_write.append(reading)
    with database.transaction():
        run = ledger.record(result, kind="coupon", now=now)
        written = readings.add_many(to_write)
    return CouponImport(
        run=run,
        written=written,
        skipped=tuple(skipped),
        quarantined=result.rejected,
        thin=tuple(thin),
    )
