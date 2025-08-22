from __future__ import annotations

from collections.abc import Callable

import pytest
from click.testing import Result

from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station

ADD_LINE = (
    "line",
    "add",
    "AL-2",
    "--name",
    "Ashfield lateral",
    "--operator",
    "Northmoor Gas",
    "--length",
    "18500 m",
    "--diameter",
    "323.9 mm",
    "--installed",
    "1974",
)


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905", "--date", "2024-05-02")
    run("post", "read", "TP-1", "--on", "-1130", "--off", "-910", "--date", "2025-03-14")


def post(**overrides: object) -> TestPoint:
    import datetime as dt

    kwargs: dict[str, object] = {
        "code": "TP-1",
        "line_code": "AL-2",
        "station": Station(100.0),
        "leads": frozenset({LeadKind.PIPE}),
        "installed_on": dt.date(1998, 5, 4),
    }
    kwargs.update(overrides)
    return TestPoint(**kwargs)  # type: ignore[arg-type]


def test_a_post_in_service_cannot_carry_a_removal_date() -> None:
    import datetime as dt

    with pytest.raises(ValidationError):
        post(removed_on=dt.date(2020, 1, 1))


def test_a_post_out_of_service_needs_one() -> None:
    with pytest.raises(ValidationError):
        post(in_service=False)


def test_a_post_cannot_be_removed_before_it_was_installed() -> None:
    import datetime as dt

    with pytest.raises(ValidationError):
        post(in_service=False, removed_on=dt.date(1900, 1, 1))


def test_a_post_can_be_moved_and_keeps_its_readings(
    run: Callable[..., Result],
) -> None:
    seed(run)
    moved = run("post", "move", "TP-1", "--to", "12+00.00")
    assert moved.exit_code == 0
    assert "moved from 10+00.00 to 12+00.00" in moved.output
    assert "2 readings kept" in moved.output
    assert "2025-03-14" in run("post", "show", "TP-1").output


def test_a_move_off_the_line_is_a_usage_error(run: Callable[..., Result]) -> None:
    seed(run)
    assert run("post", "move", "TP-1", "--to", "9999+00.00").exit_code == 2


def test_moving_a_post_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("post", "move", "TP-9", "--to", "10+00.00").exit_code == 3


def test_a_note_can_be_left_on_a_move(run: Callable[..., Result]) -> None:
    seed(run)
    run("post", "move", "TP-1", "--to", "12+00.00", "--note", "moved for the A19 widening")
    assert "moved for the A19 widening" in run("post", "show", "TP-1").output


def test_a_post_can_be_taken_out_of_service(run: Callable[..., Result]) -> None:
    seed(run)
    removed = run("post", "remove", "TP-1")
    assert removed.exit_code == 0
    assert "out of service from 2025-03-14" in removed.output
    assert "its readings stay" in removed.output


def test_a_removed_post_keeps_its_readings(run: Callable[..., Result]) -> None:
    seed(run)
    run("post", "remove", "TP-1")
    assert "2025-03-14" in run("post", "show", "TP-1").output


def test_a_removed_post_stays_in_the_listing(run: Callable[..., Result]) -> None:
    seed(run)
    run("post", "remove", "TP-1", "--on", "2025-02-01")
    listed = run("post", "list", "--line", "AL-2")
    assert "TP-1" in listed.output
    assert "removed 2025-02-01" in listed.output


def test_the_removed_posts_can_be_left_out(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "post", "add", "TP-2", "--line", "AL-2", "--at", "20+00.00", "--installed", "1998-05-04"
    )
    run("post", "remove", "TP-1")
    only_live = run("post", "list", "--line", "AL-2", "--in-service")
    assert "TP-2" in only_live.output
    assert "TP-1" not in only_live.output


def test_a_removal_before_the_post_went_in_is_refused(
    run: Callable[..., Result],
) -> None:
    seed(run)
    assert run("post", "remove", "TP-1", "--on", "1900-01-01").exit_code == 2


def test_removing_a_post_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("post", "remove", "TP-9").exit_code == 3
