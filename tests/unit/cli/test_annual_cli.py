from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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

ADD_SEGMENT = (
    "segment",
    "add",
    "AL-2-001",
    "--line",
    "AL-2",
    "--from",
    "0+00.00",
    "--to",
    "600+00.00",
    "--coating",
    "coal_tar",
    "--diameter",
    "323.9 mm",
    "--wall",
    "6.35 mm",
    "--installed",
    "1974",
)

ANNUAL = (
    "Test Post,Date,Lead,On,Off\n"
    "TP-101,2024-05-02,pipe,-1120,-905\n"
    "TP-102,2024-05-02,pipe,-1020,-780\n"
)


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    for code, station in (
        ("TP-101", "10+00.00"),
        ("TP-102", "150+00.00"),
        ("TP-103", "420+00.00"),
    ):
        run("post", "add", code, "--line", "AL-2", "--at", station, "--installed", "1998-05-04")


def test_the_annual_report_defaults_to_last_year(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "annual", "--line", "AL-2")
    assert result.exit_code == 0
    assert "annual report 2024" in result.output


def test_the_year_can_be_named(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "annual", "--line", "AL-2", "--year", "2025")
    assert "annual report 2025" in result.output


def test_the_report_carries_the_thresholds_in_force(
    run: Callable[..., Result],
) -> None:
    seed(run)
    result = run("report", "annual", "--line", "AL-2")
    assert "Measured against" in result.output
    assert "-850 mV instant off" in result.output


def test_the_posts_nobody_read_are_named_in_the_report(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    seed(run)
    target = tmp_path / "annual-2024.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    run("import", "annual", str(target))
    result = run("report", "annual", "--line", "AL-2", "--year", "2024")
    assert "TP-103" in result.output
    assert "What was not done" in result.output


def test_a_survey_file_shows_up_in_the_year_it_was_loaded(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    seed(run)
    target = tmp_path / "annual-2024.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    run("import", "annual", str(target))
    this_year = run("report", "annual", "--line", "AL-2", "--year", "2025")
    assert "1 survey files loaded" in this_year.output
    last_year = run("report", "annual", "--line", "AL-2", "--year", "2024")
    assert "0 survey files loaded" in last_year.output


def test_findings_are_split_by_year(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "150+00.00",
        "--summary",
        "under criterion",
    )
    result = run("report", "annual", "--line", "AL-2", "--year", "2025")
    assert "1 raised in the year" in result.output
    assert "1 carried forward" in result.output


def test_the_preparer_can_be_named(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "annual", "--line", "AL-2", "--by", "R Ellis")
    assert "by R Ellis" in result.output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("report", "annual", "--line", "ZZ-9").exit_code == 3


def test_a_line_with_no_posts_exits_three(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    assert run("report", "annual", "--line", "AL-2").exit_code == 3
