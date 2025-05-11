from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError, ValidationError
from dropcell.model.line import Line
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.observations import (
    Observation,
    ObservationKind,
    ObservationRepository,
)

SEEN = dt.date(2025, 3, 14)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    return database


def note(**overrides: object) -> Observation:
    kwargs: dict[str, object] = {
        "line_code": "AL-2",
        "subject": "TP-114",
        "kind": ObservationKind.ACCESS,
        "seen_on": SEEN,
        "body": "farmer will not have anybody on the field before October",
    }
    kwargs.update(overrides)
    return Observation(**kwargs)  # type: ignore[arg-type]


def test_a_note_survives_a_round_trip(register: Database) -> None:
    notes = ObservationRepository(register)
    stored = notes.add(note(seen_by="R Ellis", station=Station(1245.5)))
    assert stored.observation_id is not None
    assert notes.get(stored.observation_id) == stored


def test_a_note_with_no_subject_is_refused() -> None:
    with pytest.raises(ValidationError):
        note(subject="  ")


def test_a_note_with_no_text_is_refused() -> None:
    with pytest.raises(ValidationError):
        note(body="   ")


def test_the_line_code_is_normalised() -> None:
    assert note(line_code="al 2").line_code == "AL-2"


def test_a_note_on_a_line_that_is_not_there_is_refused(database: Database) -> None:
    with pytest.raises(ConflictError):
        ObservationRepository(database).add(note())


def test_notes_come_back_newest_first(register: Database) -> None:
    notes = ObservationRepository(register)
    notes.add(note(seen_on=dt.date(2023, 3, 14)))
    notes.add(note())
    dates = [item.seen_on for item in notes.for_line("AL-2")]
    assert dates == sorted(dates, reverse=True)


def test_notes_can_be_narrowed_by_date(register: Database) -> None:
    notes = ObservationRepository(register)
    notes.add(note(seen_on=dt.date(2023, 3, 14)))
    notes.add(note())
    recent = notes.for_line("AL-2", since=dt.date(2024, 1, 1))
    assert [item.seen_on for item in recent] == [SEEN]


def test_notes_can_be_narrowed_by_kind(register: Database) -> None:
    notes = ObservationRepository(register)
    notes.add(note())
    notes.add(note(kind=ObservationKind.DAMAGE, body="post hit by a plough"))
    damage = notes.for_line("AL-2", kind=ObservationKind.DAMAGE)
    assert [item.kind for item in damage] == [ObservationKind.DAMAGE]


def test_notes_can_be_found_by_subject(register: Database) -> None:
    notes = ObservationRepository(register)
    notes.add(note())
    notes.add(note(subject="RU-3", body="cabinet on the wrong phase"))
    assert [item.subject for item in notes.about("RU-3")] == ["RU-3"]


def test_a_subject_nobody_wrote_about_has_nothing(register: Database) -> None:
    assert ObservationRepository(register).about("TP-999") == []


def test_the_blocking_notes_are_the_ones_that_stop_the_job(
    register: Database,
) -> None:
    notes = ObservationRepository(register)
    notes.add(note())
    notes.add(note(kind=ObservationKind.GENERAL, body="repainted the post"))
    blocking = notes.blocking("AL-2")
    assert [item.kind for item in blocking] == [ObservationKind.ACCESS]


def test_only_access_and_third_party_block_work() -> None:
    blocking = {kind for kind in ObservationKind if kind.blocks_work}
    assert blocking == {ObservationKind.ACCESS, ObservationKind.THIRD_PARTY}


def test_a_note_without_a_station_comes_back_without_one(
    register: Database,
) -> None:
    notes = ObservationRepository(register)
    stored = notes.add(note())
    assert stored.station is None
    assert notes.for_line("AL-2")[0].station is None


def test_a_note_number_that_is_not_there_is_refused(register: Database) -> None:
    with pytest.raises(NotFoundError):
        ObservationRepository(register).get(99)


def test_a_note_can_be_removed(register: Database) -> None:
    notes = ObservationRepository(register)
    stored = notes.add(note())
    assert stored.observation_id is not None
    notes.delete(stored.observation_id)
    assert notes.count() == 0
    with pytest.raises(NotFoundError):
        notes.delete(stored.observation_id)


def test_deleting_a_line_takes_its_notes(register: Database) -> None:
    ObservationRepository(register).add(note())
    LineRepository(register).delete("AL-2")
    assert ObservationRepository(register).count() == 0
