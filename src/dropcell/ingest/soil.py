"""Loading four pin soundings, which arrive one spacing per row.

Every other file in this package has one row per record. A soil file has one
row per spacing and a sounding is several of them, so the rows have to be
gathered back into groups before anything can be stored. What they group on is
the place and the date, which is the only pair that identifies one set of rods
in the ground on one afternoon.

A group with one row in it is not a sounding. It is either a crew that read one
spacing and moved on, or a file whose station column has a typo on one row that
split a set in two, and both of those are worth reporting rather than storing.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.ingest.annual import SkippedRow
from dropcell.ingest.profiles import SOIL_PROFILE
from dropcell.ingest.reader import ReadResult, read_text
from dropcell.model.ids import normalise_code
from dropcell.stationing import Convention, Station
from dropcell.store.database import Database
from dropcell.store.imports import ImportLedger, ImportRun
from dropcell.store.soundings import Sounding, SoundingRepository


@dataclass(frozen=True)
class SoilImport:
    """A soil file, read and gathered into soundings."""

    run: ImportRun
    stored: int
    skipped: tuple[SkippedRow, ...]
    quarantined: int

    @property
    def clean(self) -> bool:
        """Whether every row in the file became part of a sounding."""
        return not self.skipped and self.quarantined == 0

    def reasons(self) -> tuple[str, ...]:
        """One line per group that did not become a sounding."""
        return tuple(
            f"{item.reason}" + (f" ({item.detail})" if item.detail else "")
            for item in self.skipped
        )


def gather(
    result: ReadResult,
    *,
    line_code: str,
) -> tuple[list[Sounding], list[SkippedRow]]:
    """Group rows into soundings by where and when they were taken."""
    normalised = normalise_code(line_code, kind="line code")
    groups: dict[tuple[float, dt.date], list[tuple[float, float]]] = {}
    order: list[tuple[float, dt.date]] = []
    for row in result.rows:
        station: Station = row["station"]
        key = (round(station.metres, 3), row["measured_on"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((float(row["spacing_m"]), float(row["resistance_ohm"])))
    made: list[Sounding] = []
    skipped: list[SkippedRow] = []
    for key in order:
        metres, measured_on = key
        readings = groups[key]
        try:
            made.append(
                Sounding(
                    line_code=normalised,
                    station=Station(metres),
                    measured_on=measured_on,
                    readings=tuple(readings),
                )
            )
        except ValidationError as error:
            skipped.append(
                SkippedRow(
                    0,
                    f"{metres:.1f} m on {measured_on.isoformat()}: {error.message}",
                    str(len(readings)) + " spacings",
                )
            )
    return made, skipped


def import_soil(
    database: Database,
    text: str,
    *,
    line_code: str,
    now: dt.datetime,
    source: str = "",
    convention: Convention = Convention.FOOT,
) -> SoilImport:
    """Read a soil file, gather it into soundings, and store them."""
    result = read_text(text, SOIL_PROFILE, convention=convention, source=source)
    made, skipped = gather(result, line_code=line_code)
    ledger = ImportLedger(database)
    soundings = SoundingRepository(database)
    with database.transaction():
        run = ledger.record(result, kind="soil", now=now)
    stored = 0
    for sounding in made:
        soundings.add(sounding)
        stored += 1
    return SoilImport(
        run=run,
        stored=stored,
        skipped=tuple(skipped),
        quarantined=result.rejected,
    )
