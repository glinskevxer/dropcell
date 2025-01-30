from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError, ValidationError
from dropcell.model.line import Line
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.soundings import Sounding, SoundingRepository

MEASURED = dt.date(2025, 3, 14)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    return database


def sounding(**overrides: object) -> Sounding:
    kwargs: dict[str, object] = {
        "line_code": "AL-2",
        "station": Station(1245.5),
        "measured_on": MEASURED,
        "readings": ((1.0, 20.0), (2.0, 8.0), (3.0, 5.0)),
    }
    kwargs.update(overrides)
    return Sounding(**kwargs)  # type: ignore[arg-type]


def test_a_sounding_needs_more_than_one_spacing() -> None:
    with pytest.raises(ValidationError):
        sounding(readings=((1.0, 20.0),))


def test_the_same_spacing_read_twice_is_refused() -> None:
    with pytest.raises(ValidationError):
        sounding(readings=((1.0, 20.0), (1.0, 18.0)))


def test_readings_are_sorted_by_spacing() -> None:
    made = sounding(readings=((3.0, 5.0), (1.0, 20.0), (2.0, 8.0)))
    assert [spacing for spacing, _ in made.readings] == [1.0, 2.0, 3.0]


def test_the_line_code_is_normalised() -> None:
    assert sounding(line_code="al 2").line_code == "AL-2"


def test_the_layers_come_out_of_the_barnes_method() -> None:
    layers = sounding().layers
    assert len(layers) == 3
    assert layers[0].top_m == pytest.approx(0.0)
    assert layers[-1].bottom_m == pytest.approx(3.0)


def test_a_depth_gets_the_layer_it_lies_in() -> None:
    made = sounding()
    assert made.at_depth(0.5) == pytest.approx(made.layers[0].resistivity_ohm_m)
    assert made.at_depth(2.5) == pytest.approx(made.layers[2].resistivity_ohm_m)


def test_a_depth_carries_its_corrosivity_band() -> None:
    assert sounding().corrosivity_at(1.2) in {
        "very_corrosive",
        "corrosive",
        "moderate",
        "mild",
        "benign",
    }


def test_a_sounding_survives_a_round_trip(register: Database) -> None:
    soundings = SoundingRepository(register)
    stored = soundings.add(sounding(technician="R Ellis", remark="beside the gate"))
    assert stored.sounding_id is not None
    assert soundings.get(stored.sounding_id) == stored


def test_a_sounding_on_a_line_that_is_not_there_is_refused(
    database: Database,
) -> None:
    with pytest.raises(ConflictError):
        SoundingRepository(database).add(sounding())


def test_the_same_place_on_the_same_day_is_refused(register: Database) -> None:
    soundings = SoundingRepository(register)
    soundings.add(sounding())
    with pytest.raises(ConflictError):
        soundings.add(sounding())


def test_the_same_place_on_another_day_is_fine(register: Database) -> None:
    soundings = SoundingRepository(register)
    soundings.add(sounding())
    soundings.add(sounding(measured_on=dt.date(2024, 3, 14)))
    assert soundings.count() == 2


def test_soundings_come_back_in_stationing_order(register: Database) -> None:
    soundings = SoundingRepository(register)
    soundings.add(sounding(station=Station(4000.0)))
    soundings.add(sounding())
    stations = [item.station.metres for item in soundings.for_line("AL-2")]
    assert stations == sorted(stations)


def test_the_nearest_sounding_is_the_closest_one(register: Database) -> None:
    soundings = SoundingRepository(register)
    soundings.add(sounding(station=Station(100.0)))
    soundings.add(sounding(station=Station(4000.0)))
    nearest = soundings.nearest("AL-2", Station(3800.0))
    assert nearest is not None
    assert nearest.station.metres == pytest.approx(4000.0)


def test_a_line_with_no_soundings_has_no_nearest(register: Database) -> None:
    assert SoundingRepository(register).nearest("AL-2", Station(100.0)) is None


def test_a_sounding_number_that_is_not_there_is_refused(register: Database) -> None:
    with pytest.raises(NotFoundError):
        SoundingRepository(register).get(99)


def test_deleting_a_line_takes_its_soundings_and_their_readings(
    register: Database,
) -> None:
    SoundingRepository(register).add(sounding())
    LineRepository(register).delete("AL-2")
    assert SoundingRepository(register).count() == 0
    assert register.scalar("SELECT count(*) FROM sounding_reading") == 0
