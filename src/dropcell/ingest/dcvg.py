"""Loading a gradient survey file into indications.

A gradient file is a list of defects with two millivolt numbers against each.
It is short, which is deceptive: a close interval file with three bad rows in
forty thousand loses nothing, and a gradient file with three bad rows in forty
has lost most of the survey's value, because every row on it is a place
somebody is going to dig.

So the rules here are stricter than they are for a trace. A row whose gradient
is larger than the section shift is not a small inconsistency, it is a
transcription error or a mixed up column, and it is set aside with a reason
rather than clipped to fit.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.errors import IngestError, ValidationError
from dropcell.ingest.annual import SkippedRow
from dropcell.ingest.profiles import DCVG_PROFILE
from dropcell.ingest.reader import ReadResult, read_text
from dropcell.model.ids import normalise_code
from dropcell.stationing import Convention
from dropcell.store.database import Database
from dropcell.store.imports import ImportLedger, ImportRun
from dropcell.survey.dcvg import DcvgIndication, rank_indications


@dataclass(frozen=True)
class DcvgImport:
    """A gradient file, read and turned into indications."""

    run: ImportRun
    indications: tuple[DcvgIndication, ...]
    skipped: tuple[SkippedRow, ...]
    quarantined: int

    @property
    def found(self) -> int:
        """How many defects the survey turned up."""
        return len(self.indications)

    @property
    def clean(self) -> bool:
        """Whether every row in the file became an indication."""
        return not self.skipped and self.quarantined == 0

    def reasons(self) -> tuple[str, ...]:
        """One line per row that did not become an indication."""
        return tuple(
            f"row {item.row_number}: {item.reason}"
            + (f" ({item.detail})" if item.detail else "")
            for item in self.skipped
        )


def build_indications(
    result: ReadResult,
    *,
    line_code: str,
    default_found_on: dt.date | None = None,
) -> tuple[list[DcvgIndication], list[SkippedRow]]:
    """Turn read rows into indications, setting aside the ones that cannot be."""
    normalised = normalise_code(line_code, kind="line code")
    made: list[DcvgIndication] = []
    skipped: list[SkippedRow] = []
    for offset, row in enumerate(result.rows, start=2):
        found_on = row.get("found_on") or default_found_on
        if found_on is None:
            skipped.append(SkippedRow(offset, "no date on the row and none was given"))
            continue
        try:
            made.append(
                DcvgIndication(
                    line_code=normalised,
                    station=row["station"],
                    gradient_mv=abs(float(row["gradient_mv"])),
                    section_shift_mv=abs(float(row["section_shift_mv"])),
                    found_on=found_on,
                    anodic=bool(row.get("anodic")),
                    remark=str(row.get("remark") or ""),
                )
            )
        except ValidationError as error:
            skipped.append(SkippedRow(offset, error.message, str(error.detail)))
    return made, skipped


def import_dcvg(
    database: Database,
    text: str,
    *,
    line_code: str,
    now: dt.datetime,
    source: str = "",
    convention: Convention = Convention.FOOT,
    default_found_on: dt.date | None = None,
    minimum_acceptance: float = 0.9,
) -> DcvgImport:
    """Read a gradient file, record the run, and hand back the indications."""
    result = read_text(text, DCVG_PROFILE, convention=convention, source=source)
    result.require_acceptance(minimum_acceptance)
    made, skipped = build_indications(
        result, line_code=line_code, default_found_on=default_found_on
    )
    if not made and result.total:
        raise IngestError(
            "nothing in this file could be read as an indication",
            source=source,
            rows=result.total,
            skipped=len(skipped),
        )
    ledger = ImportLedger(database)
    with database.transaction():
        run = ledger.record(result, kind="dcvg", now=now)
    return DcvgImport(
        run=run,
        indications=tuple(rank_indications(made)),
        skipped=tuple(skipped),
        quarantined=result.rejected,
    )
