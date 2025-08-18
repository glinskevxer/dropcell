from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from dropcell import __version__
from dropcell.cli.main import main


@pytest.fixture
def isolated(tmp_path: Path) -> Callable[..., Result]:
    """A runner in a directory with no settings file above it."""
    runner = CliRunner()
    register = tmp_path / "cp.sqlite"

    def invoke(*args: str, config: Path | None = None) -> Result:
        argv: Sequence[str] = ["--register", str(register), "--today", "2025-03-14"]
        if config is not None:
            argv = [*argv, "--config", str(config)]
        return runner.invoke(main, [*argv, *args])

    return invoke


def test_the_build_is_named(isolated: Callable[..., Result]) -> None:
    result = isolated("about")
    assert result.exit_code == 0
    assert __version__ in result.output
    assert "python" in result.output
    assert "schema" in result.output


def test_a_register_that_is_not_there_says_so(
    isolated: Callable[..., Result],
) -> None:
    result = isolated("about")
    assert "not there yet, run init" in result.output


def test_a_register_that_is_there_is_counted(
    isolated: Callable[..., Result],
) -> None:
    isolated("init")
    result = isolated("about")
    assert "rows in" in result.output
    assert "line" in result.output


def test_the_row_counts_move_with_the_register(
    isolated: Callable[..., Result],
) -> None:
    isolated("init")
    isolated(
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
    result = isolated("about")
    rows = {
        line.split()[0]: line.split()[-1]
        for line in result.output.splitlines()
        if line.startswith(("line ", "segment "))
    }
    assert rows["line"] == "1"
    assert rows["segment"] == "0"


def test_the_thresholds_in_force_are_printed(
    isolated: Callable[..., Result], tmp_path: Path
) -> None:
    config = tmp_path / "dropcell.toml"
    config.write_text("protection_mv = -950\npost_reach_m = 400\n", encoding="utf-8")
    result = isolated("about", config=config)
    assert "-950 mV instant off" in result.output
    assert "post reach   400 m" in result.output


def test_the_settings_file_that_was_used_is_named(
    isolated: Callable[..., Result], tmp_path: Path
) -> None:
    config = tmp_path / "dropcell.toml"
    config.write_text("protection_mv = -950\n", encoding="utf-8")
    result = isolated("about", config=config)
    assert "settings" in result.output


def test_the_register_path_is_absolute(isolated: Callable[..., Result]) -> None:
    result = isolated("about")
    line = [item for item in result.output.splitlines() if item.startswith("register")][0]
    assert line.split()[-1].startswith("/")
