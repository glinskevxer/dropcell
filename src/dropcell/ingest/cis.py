"""Loading a close interval file into a survey object.

A close interval file is not a set of records that go into tables. It is one
survey, and the useful thing to have at the end is the survey, because every
question worth asking of it is about the trace as a whole rather than about a
row.

The nominal step is worked out from the file rather than taken on trust. A crew
told to walk at a metre and a half walks at whatever their pace and the ground
allow, and the interval matters because it is what gives a single failing
reading a length. Using the value on the job sheet when the file says otherwise
puts a systematic error into every length the report prints.

The median is used rather than the mean. Skipped ground shows up as a handful
of enormous steps, and a mean over those comes out at several metres for a
survey that was walked at one.
"""

from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass

from dropcell.errors import IngestError
from dropcell.ingest.profiles import CIS_PROFILE
from dropcell.ingest.reader import ReadResult, read_text
from dropcell.model.ids import normalise_code
from dropcell.stationing import Convention
from dropcell.store.database import Database
from dropcell.store.imports import ImportLedger, ImportRun
from dropcell.survey.cis import CisPoint, CisSurvey

MIN_STEPS_FOR_INTERVAL = 3


@dataclass(frozen=True)
class CisImport:
    """A close interval file, read and turned into a survey."""

    run: ImportRun
    survey: CisSurvey
    quarantined: int

    @property
    def steps(self) -> int:
        """How many readings the survey carries."""
        return len(self.survey.points)


def infer_interval_m(points: list[CisPoint]) -> float:
    """Work the walking step out of the file itself."""
    if len(points) < MIN_STEPS_FOR_INTERVAL:
        raise IngestError(
            "too few steps to tell what interval this was walked at",
            steps=len(points),
            needed=MIN_STEPS_FOR_INTERVAL,
        )
    spacings = [
        later.station.metres - earlier.station.metres
        for earlier, later in zip(points, points[1:], strict=False)
        if later.station.metres > earlier.station.metres
    ]
    if not spacings:
        raise IngestError("every step in this file is at the same station")
    return statistics.median(spacings)


def build_survey(
    result: ReadResult,
    *,
    line_code: str,
    taken_on: dt.date,
    nominal_interval_m: float | None = None,
    technician: str = "",
    direction: str = "upstream",
) -> CisSurvey:
    """Turn read rows into a survey, working out the step if it was not given."""
    points = [
        CisPoint(
            station=row["station"],
            on_mv=float(row["on_mv"]),
            off_mv=row.get("off_mv"),
            remark=str(row.get("remark") or ""),
        )
        for row in result.rows
    ]
    if len(points) < 2:
        raise IngestError(
            "a close interval file needs more than one readable step",
            steps=len(points),
            rejected=result.rejected,
        )
    ordered = sorted(points, key=lambda point: point.station.metres)
    interval = (
        nominal_interval_m if nominal_interval_m is not None else infer_interval_m(ordered)
    )
    return CisSurvey(
        line_code=normalise_code(line_code, kind="line code"),
        taken_on=taken_on,
        points=tuple(ordered),
        nominal_interval_m=interval,
        technician=technician,
        direction=direction,
    )


def import_cis(
    database: Database,
    text: str,
    *,
    line_code: str,
    taken_on: dt.date,
    now: dt.datetime,
    source: str = "",
    convention: Convention = Convention.FOOT,
    nominal_interval_m: float | None = None,
    technician: str = "",
) -> CisImport:
    """Read a close interval file, record the run, and hand back the survey."""
    result = read_text(text, CIS_PROFILE, convention=convention, source=source)
    survey = build_survey(
        result,
        line_code=line_code,
        taken_on=taken_on,
        nominal_interval_m=nominal_interval_m,
        technician=technician,
    )
    ledger = ImportLedger(database)
    with database.transaction():
        run = ledger.record(result, kind="cis", now=now)
    return CisImport(run=run, survey=survey, quarantined=result.rejected)
