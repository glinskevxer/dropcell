"""Loading a rectifier check sheet into the register.

A check sheet is a page from a clipboard, so it carries the faults a clipboard
carries. The tap columns are often blank because nobody touched the taps and the
technician saw no reason to write down a number that had not changed. The unit
tag is sometimes the local name rather than the register tag. And the same sheet
gets typed up twice when two people are covering for each other.

Blank taps are taken as the taps the unit was last found on, which is what the
technician meant. Where there is no previous check to take them from, the row is
reported rather than guessed at, because a tap position of one on a unit that
has never been read is a fabrication that will look like a real setting forever.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from dropcell.ingest.annual import ImportOutcome, SkippedRow
from dropcell.ingest.profiles import RECTIFIER_PROFILE
from dropcell.ingest.reader import ReadResult, read_text
from dropcell.model.ids import normalise_code
from dropcell.model.rectifier import RectifierCheck
from dropcell.store.database import Database
from dropcell.store.imports import ImportLedger
from dropcell.store.rectifiers import RectifierCheckRepository, RectifierRepository


def _tap(value: Any, fallback: int | None) -> int | None:
    if value is not None:
        return int(value)
    return fallback


def import_rectifier_checks(
    database: Database,
    text: str,
    *,
    now: dt.datetime,
    source: str = "",
) -> ImportOutcome:
    """Load a rectifier check sheet, refusing a file that has been loaded before."""
    result = read_text(text, RECTIFIER_PROFILE, source=source)
    return land_rectifier_checks(database, result, now=now)


def land_rectifier_checks(
    database: Database,
    result: ReadResult,
    *,
    now: dt.datetime,
) -> ImportOutcome:
    """Write an already read check sheet into the register."""
    ledger = ImportLedger(database)
    units = RectifierRepository(database)
    checks = RectifierCheckRepository(database)
    known: dict[str, bool] = {}
    last_taps: dict[str, tuple[int, int] | None] = {}
    seen: set[tuple[str, dt.date]] = set()
    to_write: list[RectifierCheck] = []
    skipped: list[SkippedRow] = []
    for offset, row in enumerate(result.rows, start=2):
        tag = normalise_code(str(row["rectifier_tag"]), kind="rectifier tag")
        if tag not in known:
            known[tag] = units.exists(tag)
            previous = checks.latest(tag)
            last_taps[tag] = (
                None if previous is None else (previous.coarse_tap, previous.fine_tap)
            )
        if not known[tag]:
            skipped.append(SkippedRow(offset, "no rectifier with that tag", tag))
            continue
        checked_on = row["checked_on"]
        if (tag, checked_on) in seen:
            skipped.append(SkippedRow(offset, "the file reads this unit twice on one day", tag))
            continue
        if any(item.checked_on == checked_on for item in checks.for_unit(tag)):
            skipped.append(SkippedRow(offset, "already in the register", tag))
            continue
        fallback = last_taps.get(tag)
        coarse = _tap(row.get("coarse_tap"), None if fallback is None else fallback[0])
        fine = _tap(row.get("fine_tap"), None if fallback is None else fallback[1])
        if coarse is None or fine is None:
            skipped.append(
                SkippedRow(
                    offset, "no tap positions and nothing earlier to take them from", tag
                )
            )
            continue
        unit = units.get(tag)
        if not unit.is_valid_tap(coarse, fine):
            skipped.append(
                SkippedRow(
                    offset, "that tap pair is not on this unit's board", f"{coarse}/{fine}"
                )
            )
            continue
        seen.add((tag, checked_on))
        last_taps[tag] = (coarse, fine)
        to_write.append(
            RectifierCheck(
                rectifier_tag=tag,
                checked_on=checked_on,
                output_voltage_v=float(row["output_voltage_v"]),
                output_current_a=float(row["output_current_a"]),
                coarse_tap=coarse,
                fine_tap=fine,
                hour_meter=row.get("hour_meter"),
                technician=str(row.get("technician") or ""),
                comment=str(row.get("comment") or ""),
            )
        )
    with database.transaction():
        run = ledger.record(result, kind="rectifier", now=now)
        written = checks.add_many(to_write)
    return ImportOutcome(
        run=run,
        written=written,
        skipped=tuple(skipped),
        quarantined=result.rejected,
        source=result.source,
    )
