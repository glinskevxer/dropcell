"""Reading and writing four pin soundings.

A sounding is one place, one day, and several spacings, so it is two tables and
the second one is keyed on the spacing. That key is doing real work: a crew that
reads a metre spacing twice on one set of rods has either moved the rods and not
said so, or transcribed a number twice, and the Barnes arithmetic divides by the
difference between consecutive conductances, so a duplicate spacing produces a
division by zero rather than a wrong answer. Better to refuse it at the door.

Soundings are not attached to a segment. A segment carries one resistivity
because a criterion needs one number, and a sounding is a set of numbers at a
point taken on a day. Rolling the second into the first is a decision somebody
makes, with a depth in mind, and it is not made here.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.errors import NotFoundError, ValidationError
from dropcell.model.ids import normalise_code
from dropcell.soil import SoilLayer, barnes_layers, classify_corrosivity, resistivity_at_depth
from dropcell.stationing import Station
from dropcell.store.database import Database


@dataclass(frozen=True)
class Sounding:
    """One four pin set, read at several spacings on one day."""

    line_code: str
    station: Station
    measured_on: dt.date
    readings: tuple[tuple[float, float], ...]
    sounding_id: int | None = None
    technician: str = ""
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if len(self.readings) < 2:
            raise ValidationError(
                "a sounding needs at least two spacings", count=len(self.readings)
            )
        spacings = [spacing for spacing, _ in self.readings]
        if len(set(spacings)) != len(spacings):
            raise ValidationError("the same spacing was read twice", spacings=spacings)
        object.__setattr__(self, "readings", tuple(sorted(self.readings)))

    @property
    def layers(self) -> list[SoilLayer]:
        """The ground broken into layers by the Barnes method."""
        return barnes_layers(list(self.readings))

    def at_depth(self, depth_m: float) -> float:
        """The resistivity of the layer something buried at that depth lies in."""
        return resistivity_at_depth(self.layers, depth_m)

    def corrosivity_at(self, depth_m: float) -> str:
        """The band the ground at that depth falls in."""
        return str(classify_corrosivity(self.at_depth(depth_m)))


class SoundingRepository:
    """Every sounding in the register."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, sounding: Sounding) -> Sounding:
        """Insert a sounding and its readings."""
        import dataclasses

        with self.database.transaction():
            cursor = self.database.execute(
                "INSERT INTO sounding (line_code, station_m, measured_on, technician, remark)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    sounding.line_code,
                    sounding.station.metres,
                    sounding.measured_on.isoformat(),
                    sounding.technician,
                    sounding.remark,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            self.database.executemany(
                "INSERT INTO sounding_reading (sounding_id, spacing_m, resistance_ohm)"
                " VALUES (?, ?, ?)",
                [(new_id, spacing, resistance) for spacing, resistance in sounding.readings],
            )
        return dataclasses.replace(sounding, sounding_id=new_id)

    def get(self, sounding_id: int) -> Sounding:
        """One sounding by its number."""
        row = self.database.query_one(
            "SELECT id, line_code, station_m, measured_on, technician, remark"
            " FROM sounding WHERE id = ?",
            (sounding_id,),
        )
        if row is None:
            raise NotFoundError("no sounding with that number", sounding_id=sounding_id)
        return self._build(row)

    def for_line(self, line_code: str) -> list[Sounding]:
        """Every sounding on one line, in stationing order."""
        rows = self.database.query(
            "SELECT id, line_code, station_m, measured_on, technician, remark"
            " FROM sounding WHERE line_code = ? ORDER BY station_m, measured_on",
            (normalise_code(line_code, kind="line code"),),
        )
        return [self._build(row) for row in rows]

    def nearest(self, line_code: str, station: Station) -> Sounding | None:
        """The sounding closest to a place on the line."""
        found = self.for_line(line_code)
        if not found:
            return None
        return min(found, key=lambda item: abs(item.station.metres - station.metres))

    def count(self) -> int:
        """How many soundings the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM sounding") or 0)

    def _build(self, row: object) -> Sounding:
        sounding_id = int(row["id"])  # type: ignore[index]
        readings = self.database.query(
            "SELECT spacing_m, resistance_ohm FROM sounding_reading"
            " WHERE sounding_id = ? ORDER BY spacing_m",
            (sounding_id,),
        )
        return Sounding(
            line_code=str(row["line_code"]),  # type: ignore[index]
            station=Station(float(row["station_m"])),  # type: ignore[index]
            measured_on=dt.date.fromisoformat(str(row["measured_on"])),  # type: ignore[index]
            readings=tuple(
                (float(item["spacing_m"]), float(item["resistance_ohm"])) for item in readings
            ),
            sounding_id=sounding_id,
            technician=str(row["technician"]),  # type: ignore[index]
            remark=str(row["remark"]),  # type: ignore[index]
        )
