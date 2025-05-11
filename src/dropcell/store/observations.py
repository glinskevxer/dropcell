"""Free text against a place or a thing, which the rest of this has nowhere for.

Every field of every record in this register is a number or a closed
vocabulary, and that is deliberate. It is also not enough. A technician who
finds a post has been hit by a plough, or that the farmer will not let anybody
onto the field in September, or that the rectifier cabinet is wired to the
wrong phase, has something worth writing down that no column will hold.

Those notes are the difference between a register somebody uses and a register
somebody keeps a parallel spreadsheet beside. They are dated, they carry who saw
it, and they attach to whatever the note is about by its code rather than by a
foreign key, because the thing observed is sometimes a place on the line rather
than a record at all.

Nothing reads these to make a decision. They are for the person who has to go
back out there, and a tool that started deriving verdicts from free text would
be a tool that punishes people for writing anything down.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from dropcell.errors import NotFoundError, ValidationError
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station
from dropcell.store.database import Database


class ObservationKind(StrEnum):
    """Roughly what sort of note it is."""

    ACCESS = "access"
    DAMAGE = "damage"
    THIRD_PARTY = "third_party"
    ENVIRONMENT = "environment"
    EQUIPMENT = "equipment"
    GENERAL = "general"

    @property
    def blocks_work(self) -> bool:
        """Whether a note of this kind is likely to stop somebody doing the job."""
        return self in {ObservationKind.ACCESS, ObservationKind.THIRD_PARTY}


@dataclass(frozen=True)
class Observation:
    """One thing somebody saw."""

    line_code: str
    subject: str
    kind: ObservationKind
    seen_on: dt.date
    body: str
    seen_by: str = ""
    station: Station | None = None
    observation_id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if not self.subject.strip():
            raise ValidationError("an observation has to be about something")
        object.__setattr__(self, "subject", self.subject.strip())
        if not self.body.strip():
            raise ValidationError("an observation with no text is not an observation")
        object.__setattr__(self, "body", self.body.strip())


class ObservationRepository:
    """Everything anybody wrote down."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, observation: Observation) -> Observation:
        """Write one note."""
        import dataclasses

        cursor = self.database.execute(
            "INSERT INTO observation (line_code, subject, kind, seen_on, body, seen_by,"
            " station_m) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                observation.line_code,
                observation.subject,
                str(observation.kind),
                observation.seen_on.isoformat(),
                observation.body,
                observation.seen_by,
                None if observation.station is None else observation.station.metres,
            ),
        )
        return dataclasses.replace(observation, observation_id=int(cursor.lastrowid or 0))

    def get(self, observation_id: int) -> Observation:
        """One note by its number."""
        row = self.database.query_one(
            "SELECT id, line_code, subject, kind, seen_on, body, seen_by, station_m"
            " FROM observation WHERE id = ?",
            (observation_id,),
        )
        if row is None:
            raise NotFoundError("no observation with that number", id=observation_id)
        return self._build(row)

    def for_line(
        self,
        line_code: str,
        *,
        since: dt.date | None = None,
        kind: ObservationKind | None = None,
    ) -> list[Observation]:
        """Notes on one line, newest first."""
        sql = (
            "SELECT id, line_code, subject, kind, seen_on, body, seen_by, station_m"
            " FROM observation WHERE line_code = ?"
        )
        params: list[object] = [normalise_code(line_code, kind="line code")]
        if since is not None:
            sql += " AND seen_on >= ?"
            params.append(since.isoformat())
        if kind is not None:
            sql += " AND kind = ?"
            params.append(str(kind))
        sql += " ORDER BY seen_on DESC, id DESC"
        return [self._build(row) for row in self.database.query(sql, params)]

    def about(self, subject: str) -> list[Observation]:
        """Every note about one thing, newest first."""
        rows = self.database.query(
            "SELECT id, line_code, subject, kind, seen_on, body, seen_by, station_m"
            " FROM observation WHERE subject = ? ORDER BY seen_on DESC, id DESC",
            (subject.strip(),),
        )
        return [self._build(row) for row in rows]

    def blocking(self, line_code: str) -> list[Observation]:
        """Notes likely to stop somebody getting the job done."""
        return [item for item in self.for_line(line_code) if item.kind.blocks_work]

    def count(self) -> int:
        """How many notes the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM observation") or 0)

    def delete(self, observation_id: int) -> None:
        """Remove one note."""
        cursor = self.database.execute(
            "DELETE FROM observation WHERE id = ?", (observation_id,)
        )
        if cursor.rowcount == 0:
            raise NotFoundError("no observation with that number", id=observation_id)

    def _build(self, row: object) -> Observation:
        station = row["station_m"]  # type: ignore[index]
        return Observation(
            line_code=str(row["line_code"]),  # type: ignore[index]
            subject=str(row["subject"]),  # type: ignore[index]
            kind=ObservationKind(row["kind"]),  # type: ignore[index]
            seen_on=dt.date.fromisoformat(str(row["seen_on"])),  # type: ignore[index]
            body=str(row["body"]),  # type: ignore[index]
            seen_by=str(row["seen_by"]),  # type: ignore[index]
            station=None if station is None else Station(float(station)),
            observation_id=int(row["id"]),  # type: ignore[index]
        )
