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

ADD_POST = (
    "post",
    "add",
    "TP-114",
    "--line",
    "AL-2",
    "--at",
    "12+45.50",
    "--installed",
    "1998-05-04",
)


def test_a_post_can_be_added_and_listed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    added = run(*ADD_POST)
    assert added.exit_code == 0
    assert "TP-114 added at 12+45.50" in added.output
    listed = run("post", "list", "--line", "AL-2")
    assert "TP-114" in listed.output
    assert "never" in listed.output


def test_a_line_with_no_posts_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "no posts on this line" in run("post", "list", "--line", "AL-2").output


def test_a_post_off_the_end_of_the_line_is_refused(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run(
        "post",
        "add",
        "TP-9",
        "--line",
        "AL-2",
        "--at",
        "999+00.00",
        "--installed",
        "1998-05-04",
    )
    assert result.exit_code == 2
    assert "not on this line" in result.output


def test_a_post_can_carry_several_leads(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_POST, "--lead", "pipe", "--lead", "casing")
    listed = run("post", "list", "--line", "AL-2")
    assert "casing, pipe" in listed.output


def test_posts_can_be_filtered_by_lead(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_POST, "--lead", "pipe", "--lead", "casing")
    run(
        "post",
        "add",
        "TP-115",
        "--line",
        "AL-2",
        "--at",
        "20+00.00",
        "--installed",
        "1998-05-04",
    )
    only_casing = run("post", "list", "--line", "AL-2", "--lead", "casing")
    assert "TP-114" in only_casing.output
    assert "TP-115" not in only_casing.output


def test_a_reading_can_be_filed_and_shows_up(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    filed = run(
        "post", "read", "TP-114", "--on", "-1.120 V", "--off", "-0.905 V", "--by", "R Ellis"
    )
    assert filed.exit_code == 0
    assert "read at 2025-03-14" in filed.output
    shown = run("post", "show", "TP-114")
    assert "-1120" in shown.output
    assert "-905" in shown.output
    assert "R Ellis" in shown.output


def test_a_reading_defaults_to_the_working_date(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    run("post", "read", "TP-114", "--on", "-1120")
    assert "2025-03-14" in run("post", "show", "TP-114").output


def test_a_reading_against_a_lead_the_post_lacks_is_refused(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    result = run("post", "read", "TP-114", "--on", "-1120", "--lead", "casing")
    assert result.exit_code == 2
    assert "does not carry that lead" in result.output


def test_a_second_reading_on_the_same_day_is_a_conflict(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    run("post", "read", "TP-114", "--on", "-1120")
    again = run("post", "read", "TP-114", "--on", "-1100")
    assert again.exit_code == 4


def test_a_reading_against_another_electrode_is_shown_against_copper_sulfate(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    run("post", "read", "TP-114", "--on", "-1043", "--electrode", "sce")
    assert "-1120" in run("post", "show", "TP-114").output


def test_an_unread_post_says_it_has_never_been_read(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    assert "never read" in run("post", "show", "TP-114").output


def test_showing_a_post_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("post", "show", "TP-9").exit_code == 3


def test_the_last_read_date_appears_in_the_listing(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    run("post", "read", "TP-114", "--on", "-1120")
    assert "2025-03-14" in run("post", "list", "--line", "AL-2").output


def test_the_history_can_be_limited(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_POST)
    for day in ("2025-01-06", "2025-02-06", "2025-03-06"):
        run("post", "read", "TP-114", "--on", "-1120", "--date", day)
    limited = run("post", "show", "TP-114", "--limit", "1")
    assert "2025-03-06" in limited.output
    assert "2025-01-06" not in limited.output
