from __future__ import annotations

import dataclasses

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.model.enums import Commodity
from dropcell.model.line import Line
from dropcell.stationing import Convention
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository


@pytest.fixture
def lines(database: Database) -> LineRepository:
    return LineRepository(database)


def test_a_line_survives_a_round_trip(lines: LineRepository, line: Line) -> None:
    lines.add(line)
    assert lines.get("AL-2") == line


def test_the_lookup_code_is_normalised_too(lines: LineRepository, line: Line) -> None:
    lines.add(line)
    assert lines.get("al 2") == line


def test_every_field_comes_back_the_way_it_went_in(lines: LineRepository) -> None:
    metric = Line(
        code="BR-9",
        name="Brackenhill trunk",
        operator="Northmoor Gas",
        commodity=Commodity.CRUDE_OIL,
        length_m=42_000.0,
        nominal_diameter_mm=610.0,
        installed_year=1991,
        convention=Convention.METRIC,
        notes="two river crossings",
    )
    lines.add(metric)
    stored = lines.get("BR-9")
    assert stored.commodity is Commodity.CRUDE_OIL
    assert stored.convention is Convention.METRIC
    assert stored.notes == "two river crossings"


def test_adding_the_same_code_twice_is_a_conflict(lines: LineRepository, line: Line) -> None:
    lines.add(line)
    with pytest.raises(ConflictError):
        lines.add(line)


def test_saving_the_same_code_twice_replaces_it(lines: LineRepository, line: Line) -> None:
    lines.save(line)
    renamed = dataclasses.replace(line, name="Ashfield lateral, rebuilt")
    lines.save(renamed)
    assert lines.count() == 1
    assert lines.get("AL-2").name == "Ashfield lateral, rebuilt"


def test_finding_a_line_that_is_not_there_gives_nothing(lines: LineRepository) -> None:
    assert lines.find("AL-2") is None


def test_getting_a_line_that_is_not_there_names_the_code(lines: LineRepository) -> None:
    with pytest.raises(NotFoundError) as caught:
        lines.get("AL-2")
    assert caught.value.detail["code"] == "AL-2"


def test_lines_come_back_in_code_order(lines: LineRepository, line: Line) -> None:
    lines.add(line)
    lines.add(dataclasses.replace(line, code="AB-1"))
    lines.add(dataclasses.replace(line, code="ZZ-9"))
    assert [item.code for item in lines.all()] == ["AB-1", "AL-2", "ZZ-9"]


def test_an_empty_register_has_no_lines(lines: LineRepository) -> None:
    assert lines.all() == []
    assert lines.count() == 0


def test_deleting_a_line_removes_it(lines: LineRepository, line: Line) -> None:
    lines.add(line)
    lines.delete("AL-2")
    assert lines.find("AL-2") is None


def test_deleting_a_line_that_is_not_there_is_refused(lines: LineRepository) -> None:
    with pytest.raises(NotFoundError):
        lines.delete("AL-2")
