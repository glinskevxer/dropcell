from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from dropcell.cli.main import main

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

HEADER = "Station,P/S On,P/S Off,Remark\n"


def walk(offs: Sequence[float], step_ft: float = 5.0) -> str:
    rows = []
    for index, off in enumerate(offs):
        feet = index * step_ft
        major, minor = divmod(feet, 100)
        rows.append(f"{int(major)}+{minor:05.2f},-1120,{off:.0f},\n")
    return HEADER + "".join(rows)


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    target = tmp_path / "dropcell.toml"
    target.write_text(
        "\n".join(
            [
                "[dropcell]",
                'operator = "Northmoor Gas"',
                'contact = "control room 0800 111 999"',
                "protection_mv = -950",
                "post_reach_m = 400",
                "dig_budget = 1",
            ]
        ),
        encoding="utf-8",
    )
    return target


@pytest.fixture
def run_with(register: Path, config_file: Path) -> Callable[..., Result]:
    runner = CliRunner()

    def invoke(*args: str, config: Path | None = config_file) -> Result:
        argv = ["--register", str(register), "--today", "2025-03-14"]
        if config is not None:
            argv += ["--config", str(config)]
        return runner.invoke(main, [*argv, *args])

    return invoke


def test_the_settings_command_says_where_the_values_came_from(
    run_with: Callable[..., Result],
) -> None:
    result = run_with("settings")
    assert result.exit_code == 0
    assert "Northmoor Gas" in result.output
    assert "protection_mv" in result.output
    assert "-950" in result.output


def test_the_settings_command_works_with_no_file_at_all(
    run_with: Callable[..., Result],
) -> None:
    result = run_with("settings", config=None)
    assert result.exit_code == 0
    assert "protection_mv" in result.output


def test_a_settings_file_that_is_not_there_is_a_usage_error(
    register: Path, tmp_path: Path
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--register", str(register), "--config", str(tmp_path / "nope.toml"), "settings"],
    )
    assert result.exit_code != 0


def test_the_criterion_from_the_settings_is_the_one_applied(
    run_with: Callable[..., Result], tmp_path: Path
) -> None:
    run_with(*ADD_LINE)
    run_with(*ADD_SEGMENT)
    target = tmp_path / "cis.csv"
    target.write_text(walk([-905.0] * 12), encoding="utf-8")
    result = run_with("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert "1 sections" in result.output


def test_a_threshold_on_the_command_line_beats_the_settings(
    run_with: Callable[..., Result], tmp_path: Path
) -> None:
    run_with(*ADD_LINE)
    run_with(*ADD_SEGMENT)
    target = tmp_path / "cis.csv"
    target.write_text(walk([-905.0] * 12), encoding="utf-8")
    result = run_with(
        "survey",
        "cis",
        str(target),
        "--line",
        "AL-2",
        "--date",
        "2025-03-14",
        "--threshold",
        "-850 mV",
    )
    assert "0 sections" in result.output


def test_the_reach_from_the_settings_is_used_by_the_coverage_report(
    run_with: Callable[..., Result],
) -> None:
    run_with(*ADD_LINE)
    run_with(*ADD_SEGMENT)
    run_with(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    result = run_with("report", "coverage", "--line", "AL-2")
    assert "within 400 m of a post" in result.output


def test_a_reach_on_the_command_line_beats_the_settings(
    run_with: Callable[..., Result],
) -> None:
    run_with(*ADD_LINE)
    run_with(*ADD_SEGMENT)
    run_with(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    result = run_with("report", "coverage", "--line", "AL-2", "--reach", "1600 m")
    assert "within 1600 m of a post" in result.output


def test_the_register_path_can_come_from_the_settings_file(tmp_path: Path) -> None:
    target = tmp_path / "from-settings.sqlite"
    config = tmp_path / "dropcell.toml"
    config.write_text(f'register = "{target}"\n', encoding="utf-8")
    result = CliRunner().invoke(main, ["--config", str(config), "init"])
    assert result.exit_code == 0
    assert target.exists()


def test_the_register_option_beats_the_settings_file(tmp_path: Path) -> None:
    settings_target = tmp_path / "from-settings.sqlite"
    chosen = tmp_path / "chosen.sqlite"
    config = tmp_path / "dropcell.toml"
    config.write_text(f'register = "{settings_target}"\n', encoding="utf-8")
    result = CliRunner().invoke(
        main, ["--config", str(config), "--register", str(chosen), "init"]
    )
    assert result.exit_code == 0
    assert chosen.exists()
    assert not settings_target.exists()


def test_the_criterion_from_the_settings_reaches_the_protection_report(
    run_with: Callable[..., Result],
) -> None:
    run_with(*ADD_LINE)
    run_with(*ADD_SEGMENT)
    run_with(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run_with("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
    tight = run_with("report", "protection", "--line", "AL-2")
    assert "protection rate 0.0%" in tight.output
    loose = run_with("report", "protection", "--line", "AL-2", config=None)
    assert "protection rate 100.0%" in loose.output
