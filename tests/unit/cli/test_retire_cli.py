from __future__ import annotations

from collections.abc import Callable

from click.testing import Result

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


def test_a_line_can_be_retired(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    retired = run("line", "retire", "AL-2")
    assert retired.exit_code == 0
    assert "abandoned_in_place from 2025-03-14" in retired.output
    assert "the steel is still there" in retired.output


def test_a_removed_line_says_nothing_about_the_steel(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    removed = run("line", "retire", "AL-2", "--status", "removed")
    assert "removed from 2025-03-14" in removed.output
    assert "still there" not in removed.output


def test_the_retirement_date_can_be_given(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    retired = run("line", "retire", "AL-2", "--on", "2020-06-01")
    assert "from 2020-06-01" in retired.output


def test_a_retired_line_stays_in_the_listing(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("line", "retire", "AL-2")
    assert "AL-2" in run("line", "list").output
    assert "abandoned_in_place" in run("line", "list").output


def test_the_retired_lines_can_be_left_out(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "line",
        "add",
        "BR-9",
        "--name",
        "Brackenhill",
        "--operator",
        "Northmoor Gas",
        "--length",
        "1000 m",
        "--diameter",
        "323.9 mm",
        "--installed",
        "1991",
    )
    run("line", "retire", "AL-2")
    only_live = run("line", "list", "--in-service")
    assert "BR-9" in only_live.output
    assert "AL-2" not in only_live.output


def test_the_status_shows_on_the_line_page(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("line", "retire", "AL-2", "--on", "2020-06-01")
    shown = run("line", "show", "AL-2")
    assert "status      abandoned_in_place" in shown.output
    assert "retired     2020-06-01" in shown.output


def test_a_line_in_service_shows_no_retirement_date(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    shown = run("line", "show", "AL-2")
    assert "status      in_service" in shown.output
    assert "retired" not in shown.output


def test_a_retired_line_can_come_back(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("line", "retire", "AL-2")
    back = run("line", "return", "AL-2")
    assert "back in service" in back.output
    assert "AL-2" in run("line", "list", "--in-service").output


def test_a_line_cannot_be_retired_into_service(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert run("line", "retire", "AL-2", "--status", "in_service").exit_code == 2


def test_a_retirement_before_the_line_went_in_is_refused(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    result = run("line", "retire", "AL-2", "--on", "1900-01-01")
    assert result.exit_code == 2


def test_retiring_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("line", "retire", "ZZ-9").exit_code == 3
    assert run("line", "return", "ZZ-9").exit_code == 3
