from __future__ import annotations

import pytest

from dropcell.cli.common import line_at, line_span
from dropcell.errors import NotFoundError, ValidationError
from dropcell.model.line import Line
from dropcell.stationing import Convention, Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    return database


def test_a_station_is_read_in_the_line_convention(register: Database) -> None:
    found, at = line_at(register, "AL-2", "12+45.50")
    assert found.code == "AL-2"
    assert at.metres == pytest.approx(1245.5 * 0.3048)


def test_a_metric_line_reads_its_own_convention(database: Database, line: Line) -> None:
    import dataclasses

    LineRepository(database).add(
        dataclasses.replace(line, code="BR-9", convention=Convention.METRIC)
    )
    _, at = line_at(database, "BR-9", "1+000.0")
    assert at == Station(1000.0)


def test_a_station_off_the_end_is_refused(register: Database) -> None:
    with pytest.raises(ValidationError) as caught:
        line_at(register, "AL-2", "9999+00.00")
    assert caught.value.detail["code"] == "AL-2"


def test_a_line_that_is_not_there_is_refused(register: Database) -> None:
    with pytest.raises(NotFoundError):
        line_at(register, "ZZ-9", "0+00.00")


def test_a_span_with_no_end_is_a_point(register: Database) -> None:
    _, first, last = line_span(register, "AL-2", "12+45.50", None)
    assert first == last


def test_a_span_with_an_end_covers_the_stretch(register: Database) -> None:
    _, first, last = line_span(register, "AL-2", "12+45.50", "14+00.00")
    assert last.metres > first.metres


def test_a_span_ending_off_the_line_is_refused(register: Database) -> None:
    with pytest.raises(ValidationError):
        line_span(register, "AL-2", "12+45.50", "9999+00.00")
