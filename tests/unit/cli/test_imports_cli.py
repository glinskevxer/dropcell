from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
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

ANNUAL = (
    "Test Post,Date,Lead,On,Off,Native,Half Cell,Surveyor,Comment\n"
    "TP-114,2025-03-14,pipe,-1120,-905,-580,CSE-114,R Ellis,\n"
    "TP-115,2025-03-14,pipe,-1080,-870,,CSE-114,R Ellis,\n"
)


@pytest.fixture
def survey_file(tmp_path: Path) -> Path:
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    return target


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    for code, station in (("TP-114", "12+45.50"), ("TP-115", "20+00.00")):
        run("post", "add", code, "--line", "AL-2", "--at", station, "--installed", "1998-05-04")


def test_the_profiles_command_lists_what_the_build_reads(
    run: Callable[..., Result],
) -> None:
    listed = run("import", "profiles")
    assert listed.exit_code == 0
    assert "cis" in listed.output
    assert "close interval survey" in listed.output


def test_an_annual_file_loads(run: Callable[..., Result], survey_file: Path) -> None:
    seed(run)
    loaded = run("import", "annual", str(survey_file))
    assert loaded.exit_code == 0
    assert "2 rows written" in loaded.output
    assert "annual-2025.csv" in loaded.output


def test_a_dry_run_writes_nothing(run: Callable[..., Result], survey_file: Path) -> None:
    seed(run)
    dry = run("import", "annual", str(survey_file), "--dry-run")
    assert "2 rows would read" in dry.output
    assert "nothing has been loaded" in run("import", "runs").output


def test_the_same_file_twice_is_a_conflict(
    run: Callable[..., Result], survey_file: Path
) -> None:
    seed(run)
    run("import", "annual", str(survey_file))
    again = run("import", "annual", str(survey_file))
    assert again.exit_code == 4
    assert "loaded before" in again.output


def test_a_row_naming_an_unknown_post_is_reported(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    seed(run)
    target = tmp_path / "stray.csv"
    target.write_text("Test Post,Date,On\nTP-999,2025-03-14,-1120\n", encoding="utf-8")
    loaded = run("import", "annual", str(target))
    assert "0 rows written" in loaded.output
    assert "no test point with that code" in loaded.output


def test_a_broken_row_is_counted_as_held(run: Callable[..., Result], tmp_path: Path) -> None:
    seed(run)
    target = tmp_path / "dirty.csv"
    target.write_text(
        "Test Post,Date,On\nTP-114,2025-03-14,-1120\nTP-115,not a date,-1080\n",
        encoding="utf-8",
    )
    loaded = run("import", "annual", str(target))
    assert "1 rows could not be read" in loaded.output


def test_a_dry_run_names_the_rows_it_would_hold(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    target = tmp_path / "dirty.csv"
    target.write_text("Test Post,Date,On\nTP-114,not a date,-1120\n", encoding="utf-8")
    dry = run("import", "annual", str(target), "--dry-run")
    assert "0 rows would read, 1 would be held" in dry.output
    assert "taken_on" in dry.output


def test_the_runs_listing_shows_what_was_loaded(
    run: Callable[..., Result], survey_file: Path
) -> None:
    seed(run)
    run("import", "annual", str(survey_file))
    listed = run("import", "runs")
    assert "annual-2025.csv" in listed.output
    assert "2025-03-14" in listed.output


def test_the_runs_listing_can_be_narrowed_by_kind(
    run: Callable[..., Result], survey_file: Path
) -> None:
    seed(run)
    run("import", "annual", str(survey_file))
    assert "nothing has been loaded" in run("import", "runs", "--kind", "cis").output


def test_the_held_rows_of_a_run_can_be_listed(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    seed(run)
    target = tmp_path / "dirty.csv"
    target.write_text(
        "Test Post,Date,On\nTP-114,2025-03-14,-1120\nTP-115,not a date,-1080\n",
        encoding="utf-8",
    )
    run("import", "annual", str(target))
    held = run("import", "held", "1")
    assert "1 rows held" in held.output
    assert "not a date" in held.output


def test_a_run_number_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("import", "held", "99").exit_code == 3


def test_a_file_that_is_not_there_is_a_usage_error(run: Callable[..., Result]) -> None:
    assert run("import", "annual", "/nowhere/at/all.csv").exit_code == 2
