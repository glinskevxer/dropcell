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


def test_an_empty_register_says_nothing_is_open(run: Callable[..., Result]) -> None:
    result = run("report", "ageing")
    assert result.exit_code == 0
    assert "nothing open" in result.output


def test_an_open_finding_lands_in_a_bucket(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--summary",
        "under criterion",
    )
    result = run("report", "ageing")
    assert "under_criterion" in result.output
    assert "1 findings open, 0 of them for over a year" in result.output


def test_an_old_finding_lands_in_the_stale_bucket(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--summary",
        "under criterion",
        today="2023-03-14",
    )
    result = run("report", "ageing")
    assert "1 of them for over a year" in result.output


def test_a_closed_finding_leaves_the_page(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--summary",
        "under criterion",
    )
    run("finding", "clear", "F-2025-001", "--by", "R Ellis")
    assert "nothing open" in run("report", "ageing").output


def test_the_page_can_be_narrowed_to_one_line(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--summary",
        "under criterion",
    )
    result = run("report", "ageing", "--line", "AL-2")
    assert "Finding ageing, AL-2" in result.output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("report", "ageing", "--line", "ZZ-9").exit_code == 3


def test_two_kinds_are_bucketed_separately(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--summary",
        "under criterion",
    )
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "coating_defect",
        "--from",
        "20+00.00",
        "--summary",
        "category four",
    )
    result = run("report", "ageing")
    assert "under_criterion" in result.output
    assert "coating_defect" in result.output
    assert "2 findings open" in result.output
