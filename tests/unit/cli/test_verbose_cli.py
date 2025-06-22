from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from dropcell.cli.main import main


@pytest.fixture
def split_run(register: Path) -> Callable[..., Result]:
    runner = CliRunner()

    def invoke(*args: str) -> Result:
        argv: Sequence[str] = ["--register", str(register), "--today", "2025-03-14", *args]
        return runner.invoke(main, list(argv))

    return invoke


def test_no_flag_means_no_log_lines(split_run: Callable[..., Result]) -> None:
    result = split_run("init")
    assert "schema version" in result.output
    assert "opened" not in result.output


def test_one_flag_logs_the_register_being_opened(
    split_run: Callable[..., Result],
) -> None:
    result = split_run("-v", "init")
    assert "opened" in result.output
    assert "schema version" in result.output


def test_one_flag_logs_the_migrations_that_ran(
    split_run: Callable[..., Result],
) -> None:
    result = split_run("-v", "init")
    assert "migrated" in result.output
    assert "applied 1," in result.output


def test_a_second_run_logs_no_migrations(split_run: Callable[..., Result]) -> None:
    split_run("init")
    result = split_run("-v", "init")
    assert "applied" not in result.output
    assert "opened" in result.output


def test_quiet_silences_the_log_even_with_the_flag(
    split_run: Callable[..., Result],
) -> None:
    result = split_run("-v", "--quiet", "init")
    assert "opened" not in result.output


def test_an_import_is_logged(split_run: Callable[..., Result], tmp_path: Path) -> None:
    split_run(
        "line",
        "add",
        "AL-2",
        "--name",
        "x",
        "--operator",
        "y",
        "--length",
        "18500 m",
        "--diameter",
        "323.9 mm",
        "--installed",
        "1974",
    )
    split_run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    target = tmp_path / "annual.csv"
    target.write_text("Test Post,Date,On\nTP-1,2025-03-14,-1120\n", encoding="utf-8")
    result = split_run("-v", "import", "annual", str(target))
    assert "loaded annual.csv as annual" in result.output
    assert "1 rows written" in result.output
