"""Loading a depolarisation survey, which is one file for one switch off.

Everything in the file belongs to one switch off, so the two timestamps come
from the command line rather than from the rows. Putting them in every row
would let a file carry two of them, and a file carrying two switch offs is two
surveys that will be averaged into one by whoever reads the result.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.errors import IngestError
from dropcell.ingest.profiles import DEPOLARISATION_PROFILE
from dropcell.ingest.reader import read_text
from dropcell.model.ids import normalise_code
from dropcell.store.database import Database
from dropcell.store.depolarisation import DepolarisationRepository
from dropcell.store.imports import ImportLedger, ImportRun
from dropcell.survey.depolarisation import DepolarisationPoint, DepolarisationSurvey


@dataclass(frozen=True)
class DepolarisationImport:
    """A depolarisation file, read and stored."""

    run: ImportRun
    survey_id: int
    survey: DepolarisationSurvey
    quarantined: int

    @property
    def points(self) -> int:
        """How many posts the survey carries."""
        return len(self.survey.points)


def import_depolarisation(
    database: Database,
    text: str,
    *,
    line_code: str,
    switched_off_at: dt.datetime,
    read_back_at: dt.datetime,
    now: dt.datetime,
    source: str = "",
    technician: str = "",
) -> DepolarisationImport:
    """Read a depolarisation file and store it against one switch off."""
    result = read_text(text, DEPOLARISATION_PROFILE, source=source)
    seen: set[str] = set()
    points: list[DepolarisationPoint] = []
    for row in result.rows:
        code = normalise_code(str(row["test_point_code"]), kind="test point code")
        if code in seen:
            raise IngestError(
                "this file reads one post twice against the same switch off",
                test_point_code=code,
                source=source,
            )
        seen.add(code)
        points.append(
            DepolarisationPoint(
                test_point_code=code,
                off_mv=float(row["off_mv"]),
                depolarised_mv=row.get("depolarised_mv"),
                remark=str(row.get("remark") or ""),
            )
        )
    if not points:
        raise IngestError(
            "nothing in this file could be read as a post", source=source, rows=result.total
        )
    survey = DepolarisationSurvey(
        line_code=line_code,
        switched_off_at=switched_off_at,
        read_back_at=read_back_at,
        points=tuple(points),
        technician=technician,
    )
    ledger = ImportLedger(database)
    with database.transaction():
        run = ledger.record(result, kind="depolarisation", now=now)
    survey_id = DepolarisationRepository(database).add(survey)
    return DepolarisationImport(
        run=run, survey_id=survey_id, survey=survey, quarantined=result.rejected
    )
