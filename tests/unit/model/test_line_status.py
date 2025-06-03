from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.model.enums import LineStatus
from dropcell.model.line import Line
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository


def test_a_new_line_is_in_service(line: Line) -> None:
    assert line.status is LineStatus.IN_SERVICE
    assert line.is_monitored
    assert line.retired_on is None


def test_a_line_in_service_cannot_carry_a_retirement_date(line: Line) -> None:
    with pytest.raises(ValidationError):
        dataclasses.replace(line, retired_on=dt.date(2020, 1, 1))


def test_a_retired_line_needs_a_date(line: Line) -> None:
    with pytest.raises(ValidationError):
        dataclasses.replace(line, status=LineStatus.ABANDONED_IN_PLACE)


def test_a_line_cannot_be_retired_before_it_went_in(line: Line) -> None:
    with pytest.raises(ValidationError):
        dataclasses.replace(
            line,
            status=LineStatus.ABANDONED_IN_PLACE,
            retired_on=dt.date(1900, 1, 1),
        )


def test_an_abandoned_line_is_not_monitored_but_is_still_there(line: Line) -> None:
    abandoned = dataclasses.replace(
        line,
        status=LineStatus.ABANDONED_IN_PLACE,
        retired_on=dt.date(2020, 6, 1),
    )
    assert not abandoned.is_monitored
    assert abandoned.status.is_still_in_the_ground


def test_a_removed_line_is_neither(line: Line) -> None:
    removed = dataclasses.replace(
        line, status=LineStatus.REMOVED, retired_on=dt.date(2020, 6, 1)
    )
    assert not removed.is_monitored
    assert not removed.status.is_still_in_the_ground


def test_the_status_survives_a_round_trip(database: Database, line: Line) -> None:
    lines = LineRepository(database)
    abandoned = dataclasses.replace(
        line,
        status=LineStatus.ABANDONED_IN_PLACE,
        retired_on=dt.date(2020, 6, 1),
    )
    lines.add(abandoned)
    assert lines.get("AL-2") == abandoned


def test_a_line_in_service_round_trips_with_no_date(database: Database, line: Line) -> None:
    lines = LineRepository(database)
    lines.add(line)
    stored = lines.get("AL-2")
    assert stored.status is LineStatus.IN_SERVICE
    assert stored.retired_on is None


def test_the_in_service_listing_leaves_the_retired_lines_out(
    database: Database, line: Line
) -> None:
    lines = LineRepository(database)
    lines.add(line)
    lines.add(
        dataclasses.replace(
            line,
            code="BR-9",
            status=LineStatus.ABANDONED_IN_PLACE,
            retired_on=dt.date(2020, 6, 1),
        )
    )
    assert [item.code for item in lines.all()] == ["AL-2", "BR-9"]
    assert [item.code for item in lines.in_service()] == ["AL-2"]


def test_saving_a_line_can_change_its_status(database: Database, line: Line) -> None:
    lines = LineRepository(database)
    lines.save(line)
    lines.save(
        dataclasses.replace(
            line,
            status=LineStatus.REMOVED,
            retired_on=dt.date(2021, 3, 1),
        )
    )
    assert lines.count() == 1
    assert lines.get("AL-2").status is LineStatus.REMOVED
