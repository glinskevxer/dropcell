from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError, ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.testpoints import (
    TestPointRepository,
    decode_leads,
    encode_leads,
)


@pytest.fixture
def post() -> TestPoint:
    return TestPoint(
        code="TP-114",
        line_code="AL-2",
        station=Station(1245.5),
        leads=frozenset({LeadKind.PIPE, LeadKind.CASING}),
        installed_on=dt.date(1998, 5, 4),
    )


@pytest.fixture
def posts(database: Database, line: Line) -> TestPointRepository:
    LineRepository(database).add(line)
    return TestPointRepository(database)


def test_a_lead_set_serialises_in_sorted_order() -> None:
    assert encode_leads(frozenset({LeadKind.PIPE, LeadKind.ANODE})) == "anode,pipe"
    assert encode_leads(frozenset({LeadKind.ANODE, LeadKind.PIPE})) == "anode,pipe"


def test_a_lead_set_round_trips_through_its_string() -> None:
    leads = frozenset({LeadKind.PIPE, LeadKind.COUPON})
    assert decode_leads(encode_leads(leads)) == leads


def test_a_stored_lead_string_that_is_empty_is_refused() -> None:
    with pytest.raises(ValidationError):
        decode_leads("  ")


def test_a_stored_lead_this_build_does_not_know_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        decode_leads("pipe,antenna")
    assert caught.value.detail["raw"] == "pipe,antenna"


def test_a_post_survives_a_round_trip(posts: TestPointRepository, post: TestPoint) -> None:
    posts.add(post)
    assert posts.get("TP-114") == post


def test_the_permanent_cell_flag_comes_back_as_a_bool(
    posts: TestPointRepository, post: TestPoint
) -> None:
    posts.add(dataclasses.replace(post, permanent_reference_cell=True))
    assert posts.get("TP-114").permanent_reference_cell is True


def test_two_posts_with_the_same_code_are_refused(
    posts: TestPointRepository, post: TestPoint
) -> None:
    posts.add(post)
    with pytest.raises(ConflictError):
        posts.add(post)


def test_a_post_on_a_line_that_is_not_there_is_refused(
    posts: TestPointRepository, post: TestPoint
) -> None:
    with pytest.raises(ConflictError):
        posts.add(dataclasses.replace(post, line_code="ZZ-9"))


def test_posts_come_back_in_stationing_order(
    posts: TestPointRepository, post: TestPoint
) -> None:
    posts.add(dataclasses.replace(post, code="TP-3", station=Station(4000.0)))
    posts.add(dataclasses.replace(post, code="TP-1", station=Station(100.0)))
    posts.add(dataclasses.replace(post, code="TP-2", station=Station(2000.0)))
    assert [item.code for item in posts.for_line("AL-2")] == ["TP-1", "TP-2", "TP-3"]


def test_a_range_query_takes_the_posts_inside_it(
    posts: TestPointRepository, post: TestPoint
) -> None:
    posts.add(dataclasses.replace(post, code="TP-1", station=Station(100.0)))
    posts.add(dataclasses.replace(post, code="TP-2", station=Station(2000.0)))
    posts.add(dataclasses.replace(post, code="TP-3", station=Station(4000.0)))
    inside = posts.in_range("AL-2", StationRange(Station(100.0), Station(2000.0)))
    assert [item.code for item in inside] == ["TP-1", "TP-2"]


def test_filtering_by_lead_keeps_only_the_posts_that_carry_it(
    posts: TestPointRepository, post: TestPoint
) -> None:
    posts.add(post)
    posts.add(
        dataclasses.replace(
            post, code="TP-115", station=Station(2000.0), leads=frozenset({LeadKind.PIPE})
        )
    )
    assert [p.code for p in posts.with_lead("AL-2", LeadKind.CASING)] == ["TP-114"]
    assert len(posts.with_lead("AL-2", LeadKind.PIPE)) == 2


def test_a_missing_post_is_named_in_the_refusal(posts: TestPointRepository) -> None:
    assert posts.find("TP-114") is None
    with pytest.raises(NotFoundError) as caught:
        posts.get("TP-114")
    assert caught.value.detail["code"] == "TP-114"


def test_deleting_a_post_removes_it(posts: TestPointRepository, post: TestPoint) -> None:
    posts.add(post)
    posts.delete("TP-114")
    assert posts.count() == 0
    with pytest.raises(NotFoundError):
        posts.delete("TP-114")


def test_deleting_a_line_takes_its_posts_with_it(
    database: Database, posts: TestPointRepository, post: TestPoint
) -> None:
    posts.add(post)
    LineRepository(database).delete("AL-2")
    assert posts.count() == 0
