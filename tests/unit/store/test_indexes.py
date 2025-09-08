"""The indexes the reports rely on, and proof that SQLite is using them.

An index that exists and is never chosen is worse than no index: it costs on
every write and buys nothing, and it looks like the problem is solved. So these
tests read the query plan rather than the schema, and they name the query each
index was added for.

The plans are read with EXPLAIN QUERY PLAN, which is stable enough to test on
because it reports which index a step used rather than how the step is
implemented. A plan that stops naming an index has stopped using it, and that is
exactly the change worth failing on.
"""

from __future__ import annotations

import datetime as dt

import pytest

from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.testpoints import TestPointRepository


def plan(database: Database, sql: str, parameters: tuple[object, ...] = ()) -> str:
    """What SQLite says it will do, as one string."""
    rows = database.query(f"EXPLAIN QUERY PLAN {sql}", parameters)
    return " ".join(str(row["detail"]) for row in rows)


@pytest.fixture
def loaded(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    posts = TestPointRepository(database)
    readings = ReadingRepository(database)
    batch: list[Reading] = []
    for index in range(40):
        code = f"TP-{index:03d}"
        posts.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(float(index) * 100.0),
                leads=frozenset({LeadKind.PIPE, LeadKind.CASING}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
        for year in (2023, 2024, 2025):
            for lead in (LeadKind.PIPE, LeadKind.CASING):
                batch.append(
                    Reading(
                        test_point_code=code,
                        lead=lead,
                        taken_on=dt.date(year, 3, 14),
                        on_mv=-1120.0,
                        off_mv=-905.0,
                    )
                )
    readings.add_many(batch)
    database.execute("ANALYZE")
    return database


def test_every_index_the_migrations_declare_is_there(database: Database) -> None:
    rows = database.query(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
    )
    names = {str(row["name"]) for row in rows}
    for expected in (
        "reading_by_point_lead",
        "finding_by_kind",
        "observation_by_kind",
        "coupon_reading_latest",
    ):
        assert expected in names


def test_reading_one_lead_at_one_post_uses_the_lead_index(loaded: Database) -> None:
    detail = plan(
        loaded,
        "SELECT * FROM reading WHERE test_point_code = ? AND lead = ? ORDER BY taken_on",
        ("TP-001", "pipe"),
    )
    assert "reading_by_point_lead" in detail


def test_the_latest_reading_per_post_uses_it_too(loaded: Database) -> None:
    detail = plan(
        loaded,
        "SELECT r.taken_on FROM reading r JOIN test_point t ON t.code = r.test_point_code"
        " WHERE t.line_code = ? AND r.lead = ?"
        " AND r.taken_on = (SELECT max(taken_on) FROM reading"
        " WHERE test_point_code = r.test_point_code AND lead = r.lead)",
        ("AL-2", "pipe"),
    )
    assert "reading_by_point_lead" in detail


def test_nothing_in_that_plan_scans_the_readings(loaded: Database) -> None:
    detail = plan(
        loaded,
        "SELECT r.taken_on FROM reading r JOIN test_point t ON t.code = r.test_point_code"
        " WHERE t.line_code = ? AND r.lead = ?",
        ("AL-2", "pipe"),
    )
    assert "SCAN reading" not in detail


def test_the_open_exception_register_uses_an_index(database: Database) -> None:
    detail = plan(
        database,
        "SELECT code FROM finding WHERE state IN ('open', 'scheduled')"
        " ORDER BY due_by IS NULL, due_by, code",
    )
    assert "finding_by_state" in detail or "finding_by_kind" in detail


def test_the_lead_index_still_answers_a_query_without_the_lead(
    loaded: Database,
) -> None:
    detail = plan(loaded, "SELECT * FROM reading WHERE test_point_code = ?", ("TP-001",))
    assert "reading_by_point" in detail


def test_the_latest_reading_still_comes_back_right(loaded: Database) -> None:
    readings = ReadingRepository(loaded)
    latest = readings.latest_for_point("TP-001", LeadKind.PIPE)
    assert latest is not None
    assert latest.taken_on == dt.date(2025, 3, 14)


def test_the_lookup_per_line_still_comes_back_right(loaded: Database) -> None:
    latest = ReadingRepository(loaded).latest_per_point("AL-2", LeadKind.PIPE)
    assert len(latest) == 40
    assert all(item.taken_on.year == 2025 for item in latest.values())


def test_the_casing_readings_are_kept_apart_from_the_pipe_ones(
    loaded: Database,
) -> None:
    pipe = ReadingRepository(loaded).latest_per_point("AL-2", LeadKind.PIPE)
    casing = ReadingRepository(loaded).latest_per_point("AL-2", LeadKind.CASING)
    assert set(pipe) == set(casing)
    assert all(item.lead is LeadKind.PIPE for item in pipe.values())
    assert all(item.lead is LeadKind.CASING for item in casing.values())
