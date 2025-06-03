from __future__ import annotations

import pytest

from dropcell.errors import NotFoundError, ValidationError
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository


def test_every_code_keyed_repository_names_its_own_record_kind(
    database: Database,
) -> None:
    assert LineRepository(database).noun == "line"
    assert SegmentRepository(database).noun == "segment"
    assert TestPointRepository(database).noun == "test point"


def test_the_code_kind_used_in_errors_follows_the_noun(database: Database) -> None:
    with pytest.raises(ValidationError) as caught:
        TestPointRepository(database).find("  ")
    assert "test point code" in caught.value.message


def test_exists_answers_without_building_the_record(database: Database, line: Line) -> None:
    lines = LineRepository(database)
    assert not lines.exists("AL-2")
    lines.add(line)
    assert lines.exists("AL-2")
    assert lines.exists("al 2")


def test_the_refusal_carries_the_normalised_code_not_the_typed_one(
    database: Database,
) -> None:
    with pytest.raises(NotFoundError) as caught:
        LineRepository(database).get("al 2")
    assert caught.value.detail["code"] == "AL-2"


def test_deleting_by_a_scruffy_code_still_finds_the_record(
    database: Database, line: Line
) -> None:
    lines = LineRepository(database)
    lines.add(line)
    lines.delete(" al-2 ")
    assert lines.count() == 0


def test_listing_uses_each_repository_own_order(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    segments = SegmentRepository(database)
    segments.add(segment)
    assert segments.order_by == "line_code, start_m"
    assert [item.code for item in segments.all()] == ["AL-2-004"]


def test_the_base_refuses_to_build_a_record_it_was_not_told_how_to(
    database: Database,
) -> None:
    from dropcell.store.base import Repository

    class Bare(Repository[str]):
        table = "line"
        columns = "code"
        noun = "thing"

    database.execute(
        "INSERT INTO line VALUES ('AL-2', 'a', 'b', 'natural_gas', 1, 1, 1974, 'foot',"
        " '', 'in_service', NULL)"
    )
    with pytest.raises(NotImplementedError):
        Bare(database).all()
