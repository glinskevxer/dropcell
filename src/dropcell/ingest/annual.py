"""Loading an annual survey file into the register.

Reading the file is one problem and it is solved elsewhere. Landing the rows is
a different one, and it fails for reasons that have nothing to do with the file
being malformed.

A row can name a post that is not in the register. That is usually a typo, and
occasionally it is a post somebody installed and never told the office about,
and neither of those should be decided by an import script. It is reported.

A row can duplicate a reading already stored. That happens when a crew resends a
day's work with two more posts added to the end, which is a completely
reasonable thing for them to do. Refusing the whole file over it would mean the
two new posts never land, so the duplicates are counted and skipped and the new
ones go in.

Nothing is written unless the whole batch can be written. A half loaded survey
is worse than none, because the missing half is invisible.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from dropcell.electrodes import Electrode
from dropcell.errors import IngestError
from dropcell.ingest.profiles import ANNUAL_PROFILE
from dropcell.ingest.reader import ReadResult, read_text
from dropcell.model.enums import LeadKind
from dropcell.model.ids import normalise_code
from dropcell.model.reading import Reading
from dropcell.store.database import Database
from dropcell.store.imports import ImportLedger, ImportRun
from dropcell.store.readings import ReadingRepository
from dropcell.store.testpoints import TestPointRepository


@dataclass(frozen=True)
class SkippedRow:
    """A row that read cleanly and still could not be stored."""

    row_number: int
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class ImportOutcome:
    """What one load did to the register."""

    run: ImportRun
    written: int
    skipped: tuple[SkippedRow, ...] = ()
    quarantined: int = 0
    source: str = field(default="", compare=False)

    @property
    def clean(self) -> bool:
        """Whether every row in the file landed."""
        return not self.skipped and self.quarantined == 0

    def reasons(self) -> tuple[str, ...]:
        """One line per row that did not land."""
        return tuple(
            f"row {item.row_number}: {item.reason}"
            + (f" ({item.detail})" if item.detail else "")
            for item in self.skipped
        )


def _lead_from(value: Any) -> LeadKind:
    if value is None or not str(value).strip():
        return LeadKind.PIPE
    try:
        return LeadKind(str(value).strip().lower())
    except ValueError as exc:
        raise IngestError("that is not a lead this build knows", lead=str(value)) from exc


def import_annual(
    database: Database,
    text: str,
    *,
    now: dt.datetime,
    source: str = "",
    electrode: Electrode = Electrode.CSE,
) -> ImportOutcome:
    """Load an annual survey file, refusing a file that has been loaded before."""
    result = read_text(text, ANNUAL_PROFILE, source=source)
    return land_annual(database, result, now=now, electrode=electrode)


def land_annual(
    database: Database,
    result: ReadResult,
    *,
    now: dt.datetime,
    electrode: Electrode = Electrode.CSE,
) -> ImportOutcome:
    """Write an already read annual survey into the register."""
    ledger = ImportLedger(database)
    posts = TestPointRepository(database)
    readings = ReadingRepository(database)
    known: dict[str, bool] = {}
    seen: set[tuple[str, str, dt.date]] = set()
    to_write: list[Reading] = []
    skipped: list[SkippedRow] = []
    for offset, row in enumerate(result.rows, start=2):
        code = normalise_code(str(row["test_point_code"]), kind="test point code")
        if code not in known:
            known[code] = posts.exists(code)
        if not known[code]:
            skipped.append(SkippedRow(offset, "no test point with that code", code))
            continue
        lead = _lead_from(row.get("lead"))
        taken_on = row["taken_on"]
        key = (code, str(lead), taken_on)
        if key in seen:
            skipped.append(
                SkippedRow(offset, "the file reads this lead twice on one day", code)
            )
            continue
        if readings.last_read_on(code, lead) is not None and any(
            existing.taken_on == taken_on
            for existing in readings.for_point(code, lead=lead, since=taken_on, until=taken_on)
        ):
            skipped.append(SkippedRow(offset, "already in the register", code))
            continue
        seen.add(key)
        to_write.append(
            Reading(
                test_point_code=code,
                lead=lead,
                taken_on=taken_on,
                on_mv=float(row["on_mv"]),
                off_mv=row.get("off_mv"),
                native_mv=row.get("native_mv"),
                electrode=electrode,
                cell_serial=str(row.get("cell_serial") or ""),
                technician=str(row.get("technician") or ""),
                comment=str(row.get("comment") or ""),
            )
        )
    with database.transaction():
        run = ledger.record(result, kind="annual", now=now)
        written = readings.add_many(to_write)
    return ImportOutcome(
        run=run,
        written=written,
        skipped=tuple(skipped),
        quarantined=result.rejected,
        source=result.source,
    )
