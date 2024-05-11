from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.electrodes import Electrode
from dropcell.errors import ConflictError
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.testpoint import Reading, TestPoint
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.testpoints import TestPointRepository


@pytest.fixture
def readings(database: Database, line: Line) -> ReadingRepository:
    LineRepository(database).add(line)
    posts = TestPointRepository(database)
    for code, station in (("TP-114", 1245.5), ("TP-115", 2400.0)):
        posts.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(station),
                leads=frozenset({LeadKind.PIPE, LeadKind.CASING}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
    return ReadingRepository(database)


def make_reading(**overrides: object) -> Reading:
    kwargs: dict[str, object] = {
        "test_point_code": "TP-114",
        "lead": LeadKind.PIPE,
        "taken_on": dt.date(2025, 3, 14),
        "on_mv": -1120.0,
        "off_mv": -905.0,
    }
    kwargs.update(overrides)
    return Reading(**kwargs)  # type: ignore[arg-type]


def test_a_reading_survives_a_round_trip(readings: ReadingRepository) -> None:
    reading = make_reading(native_mv=-580.0, electrode=Electrode.SCE, technician="R Ellis")
    readings.add(reading)
    assert readings.for_point("TP-114") == [reading]


def test_a_reading_without_an_off_stores_a_null(readings: ReadingRepository) -> None:
    readings.add(make_reading(off_mv=None))
    assert readings.for_point("TP-114")[0].off_mv is None


def test_the_same_lead_read_twice_in_a_day_is_refused(readings: ReadingRepository) -> None:
    readings.add(make_reading())
    with pytest.raises(ConflictError):
        readings.add(make_reading(on_mv=-1100.0))


def test_two_leads_at_one_post_on_one_day_are_fine(readings: ReadingRepository) -> None:
    readings.add(make_reading())
    readings.add(make_reading(lead=LeadKind.CASING))
    assert len(readings.for_point("TP-114")) == 2


def test_a_reading_at_a_post_that_is_not_there_is_refused(
    readings: ReadingRepository,
) -> None:
    with pytest.raises(ConflictError):
        readings.add(make_reading(test_point_code="TP-999"))


def test_a_batch_reports_how_many_landed(readings: ReadingRepository) -> None:
    batch = [
        make_reading(taken_on=dt.date(2024, 3, 14)),
        make_reading(taken_on=dt.date(2025, 3, 14)),
    ]
    assert readings.add_many(batch) == 2
    assert readings.count() == 2


def test_an_empty_batch_writes_nothing(readings: ReadingRepository) -> None:
    assert readings.add_many([]) == 0


def test_readings_at_a_post_come_back_oldest_first(readings: ReadingRepository) -> None:
    readings.add(make_reading(taken_on=dt.date(2025, 3, 14)))
    readings.add(make_reading(taken_on=dt.date(2023, 6, 1)))
    readings.add(make_reading(taken_on=dt.date(2024, 5, 2)))
    dates = [item.taken_on for item in readings.for_point("TP-114")]
    assert dates == sorted(dates)


def test_a_lead_filter_narrows_the_history(readings: ReadingRepository) -> None:
    readings.add(make_reading())
    readings.add(make_reading(lead=LeadKind.CASING))
    only_pipe = readings.for_point("TP-114", lead=LeadKind.PIPE)
    assert [item.lead for item in only_pipe] == [LeadKind.PIPE]


def test_date_bounds_are_inclusive(readings: ReadingRepository) -> None:
    for day in (dt.date(2023, 1, 1), dt.date(2024, 1, 1), dt.date(2025, 1, 1)):
        readings.add(make_reading(taken_on=day))
    window = readings.for_point("TP-114", since=dt.date(2023, 1, 1), until=dt.date(2024, 1, 1))
    assert [item.taken_on for item in window] == [dt.date(2023, 1, 1), dt.date(2024, 1, 1)]


def test_the_latest_reading_is_the_most_recent_one(readings: ReadingRepository) -> None:
    readings.add(make_reading(taken_on=dt.date(2023, 6, 1)))
    readings.add(make_reading(taken_on=dt.date(2025, 3, 14)))
    latest = readings.latest_for_point("TP-114", LeadKind.PIPE)
    assert latest is not None
    assert latest.taken_on == dt.date(2025, 3, 14)


def test_a_lead_never_read_has_no_latest(readings: ReadingRepository) -> None:
    assert readings.latest_for_point("TP-114", LeadKind.PIPE) is None
    assert readings.last_read_on("TP-114", LeadKind.PIPE) is None


def test_the_last_read_date_is_what_the_schedule_runs_off(
    readings: ReadingRepository,
) -> None:
    readings.add(make_reading(taken_on=dt.date(2024, 11, 3)))
    assert readings.last_read_on("TP-114", LeadKind.PIPE) == dt.date(2024, 11, 3)


def test_a_line_query_walks_the_posts_in_stationing_order(
    readings: ReadingRepository,
) -> None:
    readings.add(make_reading(test_point_code="TP-115"))
    readings.add(make_reading(test_point_code="TP-114"))
    codes = [item.test_point_code for item in readings.for_line("AL-2")]
    assert codes == ["TP-114", "TP-115"]


def test_a_line_query_takes_the_same_filters(readings: ReadingRepository) -> None:
    readings.add(make_reading(taken_on=dt.date(2023, 6, 1)))
    readings.add(make_reading(taken_on=dt.date(2025, 3, 14), lead=LeadKind.CASING))
    narrowed = readings.for_line("AL-2", lead=LeadKind.CASING, since=dt.date(2024, 1, 1))
    assert [item.taken_on for item in narrowed] == [dt.date(2025, 3, 14)]


def test_dropping_a_post_history_reports_how_many_went(
    readings: ReadingRepository,
) -> None:
    readings.add(make_reading())
    readings.add(make_reading(lead=LeadKind.CASING))
    assert readings.delete_for_point("TP-114") == 2
    assert readings.count() == 0


def test_deleting_a_post_takes_its_readings_with_it(
    database: Database, readings: ReadingRepository
) -> None:
    readings.add(make_reading())
    TestPointRepository(database).delete("TP-114")
    assert readings.count() == 0


def test_the_electrode_comes_back_as_an_enum(readings: ReadingRepository) -> None:
    readings.add(make_reading(electrode=Electrode.SILVER_CHLORIDE))
    stored = readings.for_point("TP-114")[0]
    assert stored.electrode is Electrode.SILVER_CHLORIDE


def test_a_replaced_reading_can_be_stored_under_a_different_date(
    readings: ReadingRepository,
) -> None:
    first = make_reading()
    readings.add(first)
    readings.add(dataclasses.replace(first, taken_on=dt.date(2025, 3, 15)))
    assert readings.count() == 2
