from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.model.enums import AnodeMaterial, GroundbedKind
from dropcell.model.groundbed import Groundbed
from dropcell.model.line import Line
from dropcell.model.rectifier import Rectifier, RectifierCheck
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.rectifiers import (
    GroundbedRepository,
    RectifierCheckRepository,
    RectifierRepository,
)


def make_bed(**overrides: object) -> Groundbed:
    kwargs: dict[str, object] = {
        "code": "GB-3",
        "kind": GroundbedKind.DEEP_WELL,
        "material": AnodeMaterial.HIGH_SILICON_IRON,
        "anode_count": 10,
        "anode_mass_kg": 20.0,
        "installed_on": dt.date(2004, 9, 1),
        "design_current_a": 15.0,
    }
    kwargs.update(overrides)
    return Groundbed(**kwargs)  # type: ignore[arg-type]


def make_unit(**overrides: object) -> Rectifier:
    kwargs: dict[str, object] = {
        "tag": "RU-3",
        "line_code": "AL-2",
        "station": Station(4210.0),
        "groundbed_code": "GB-3",
        "rated_voltage_v": 24.0,
        "rated_current_a": 20.0,
        "coarse_taps": 5,
        "fine_taps": 4,
        "installed_on": dt.date(2004, 9, 1),
    }
    kwargs.update(overrides)
    return Rectifier(**kwargs)  # type: ignore[arg-type]


def make_check(**overrides: object) -> RectifierCheck:
    kwargs: dict[str, object] = {
        "rectifier_tag": "RU-3",
        "checked_on": dt.date(2025, 3, 14),
        "output_voltage_v": 18.5,
        "output_current_a": 12.4,
        "coarse_tap": 3,
        "fine_tap": 2,
    }
    kwargs.update(overrides)
    return RectifierCheck(**kwargs)  # type: ignore[arg-type]


@pytest.fixture
def wired(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    GroundbedRepository(database).add(make_bed())
    RectifierRepository(database).add(make_unit())
    return database


def test_a_groundbed_survives_a_round_trip(database: Database) -> None:
    beds = GroundbedRepository(database)
    beds.add(make_bed(description="deep well behind the substation"))
    assert beds.get("GB-3") == make_bed(description="deep well behind the substation")


def test_a_rectifier_survives_a_round_trip(wired: Database) -> None:
    assert RectifierRepository(wired).get("RU-3") == make_unit()


def test_a_rectifier_is_looked_up_by_its_tag(wired: Database) -> None:
    assert RectifierRepository(wired).get("ru 3").tag == "RU-3"
    assert RectifierRepository(wired).code_kind == "rectifier tag"


def test_a_rectifier_on_a_bed_that_is_not_there_is_refused(
    database: Database, line: Line
) -> None:
    LineRepository(database).add(line)
    with pytest.raises(ConflictError):
        RectifierRepository(database).add(make_unit())


def test_units_on_a_line_come_back_in_stationing_order(wired: Database) -> None:
    units = RectifierRepository(wired)
    units.add(make_unit(tag="RU-1", station=Station(100.0)))
    assert [item.tag for item in units.for_line("AL-2")] == ["RU-1", "RU-3"]


def test_units_can_be_found_by_the_bed_they_feed(wired: Database) -> None:
    units = RectifierRepository(wired)
    units.add(make_unit(tag="RU-4", station=Station(9000.0)))
    assert [item.tag for item in units.on_groundbed("GB-3")] == ["RU-3", "RU-4"]


def test_a_missing_rectifier_is_named_in_the_refusal(wired: Database) -> None:
    with pytest.raises(NotFoundError) as caught:
        RectifierRepository(wired).get("RU-9")
    assert caught.value.detail["code"] == "RU-9"


def test_a_check_survives_a_round_trip(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    original = make_check(hour_meter=41_233.5, technician="R Ellis")
    checks.add(original)
    assert checks.for_unit("RU-3") == [original]


def test_a_check_without_an_hour_meter_stores_a_null(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    checks.add(make_check())
    assert checks.for_unit("RU-3")[0].hour_meter is None


def test_two_checks_on_one_unit_on_one_day_are_refused(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    checks.add(make_check())
    with pytest.raises(ConflictError):
        checks.add(make_check(output_current_a=9.0))


def test_a_check_on_a_unit_that_is_not_there_is_refused(wired: Database) -> None:
    with pytest.raises(ConflictError):
        RectifierCheckRepository(wired).add(make_check(rectifier_tag="RU-9"))


def test_a_batch_of_checks_reports_how_many_landed(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    batch = [
        make_check(checked_on=dt.date(2025, 1, 6)),
        make_check(checked_on=dt.date(2025, 3, 14)),
    ]
    assert checks.add_many(batch) == 2
    assert checks.count() == 2


def test_an_empty_batch_writes_nothing(wired: Database) -> None:
    assert RectifierCheckRepository(wired).add_many([]) == 0


def test_checks_come_back_oldest_first_and_can_be_bounded(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    for day in (dt.date(2025, 5, 1), dt.date(2025, 1, 6), dt.date(2025, 3, 14)):
        checks.add(make_check(checked_on=day))
    assert [item.checked_on for item in checks.for_unit("RU-3")] == [
        dt.date(2025, 1, 6),
        dt.date(2025, 3, 14),
        dt.date(2025, 5, 1),
    ]
    window = checks.for_unit("RU-3", since=dt.date(2025, 2, 1), until=dt.date(2025, 4, 1))
    assert [item.checked_on for item in window] == [dt.date(2025, 3, 14)]


def test_the_latest_check_is_the_most_recent_one(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    checks.add(make_check(checked_on=dt.date(2025, 1, 6)))
    checks.add(make_check(checked_on=dt.date(2025, 3, 14)))
    latest = checks.latest("RU-3")
    assert latest is not None
    assert latest.checked_on == dt.date(2025, 3, 14)


def test_a_unit_never_checked_has_no_latest(wired: Database) -> None:
    assert RectifierCheckRepository(wired).latest("RU-3") is None
    assert RectifierCheckRepository(wired).visit_dates("RU-3") == []


def test_the_visit_dates_are_what_the_schedule_reads(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    checks.add(make_check(checked_on=dt.date(2025, 1, 6)))
    checks.add(make_check(checked_on=dt.date(2025, 3, 14)))
    assert checks.visit_dates("RU-3") == [dt.date(2025, 1, 6), dt.date(2025, 3, 14)]


def test_deleting_a_unit_takes_its_checks_with_it(wired: Database) -> None:
    checks = RectifierCheckRepository(wired)
    checks.add(make_check())
    RectifierRepository(wired).delete("RU-3")
    assert checks.count() == 0


def test_a_bed_cannot_be_dropped_while_a_unit_still_points_at_it(
    wired: Database,
) -> None:
    with pytest.raises(ConflictError):
        GroundbedRepository(wired).delete("GB-3")


def test_a_galvanic_bed_round_trips_its_material(database: Database) -> None:
    beds = GroundbedRepository(database)
    beds.add(
        dataclasses.replace(
            make_bed(),
            code="GB-9",
            kind=GroundbedKind.GALVANIC_STRING,
            material=AnodeMaterial.MAGNESIUM,
        )
    )
    assert beds.get("GB-9").material is AnodeMaterial.MAGNESIUM
