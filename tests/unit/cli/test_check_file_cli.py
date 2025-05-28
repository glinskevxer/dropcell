from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from click.testing import Result

CIS = "Station,P/S On,P/S Off\n0+00.00,-1120,-905\n0+05.00,-1118,-902\n"


def test_a_file_is_identified_without_a_register(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    target = tmp_path / "mystery.csv"
    target.write_text(CIS, encoding="utf-8")
    result = run("import", "check", str(target))
    assert result.exit_code == 0
    assert "best match is cis" in result.output
    assert "2 rows would read" in result.output


def test_the_column_mapping_is_printed(run: Callable[..., Result], tmp_path: Path) -> None:
    target = tmp_path / "mystery.csv"
    target.write_text(CIS, encoding="utf-8")
    result = run("import", "check", str(target))
    assert "Station -> station" in result.output
    assert "P/S Off -> off_mv" in result.output


def test_a_column_nothing_uses_is_named(run: Callable[..., Result], tmp_path: Path) -> None:
    target = tmp_path / "mystery.csv"
    target.write_text("Station,P/S On,Operator Notes\n0+00.00,-1120,x\n", encoding="utf-8")
    result = run("import", "check", str(target))
    assert "Operator Notes -> nothing" in result.output


def test_a_file_nothing_can_read_says_so(run: Callable[..., Result], tmp_path: Path) -> None:
    target = tmp_path / "mystery.csv"
    target.write_text("Colour,Shape\nred,round\n", encoding="utf-8")
    result = run("import", "check", str(target))
    assert "no profile this build ships can read that file" in result.output


def test_one_profile_can_be_named(run: Callable[..., Result], tmp_path: Path) -> None:
    target = tmp_path / "mystery.csv"
    target.write_text(CIS, encoding="utf-8")
    result = run("import", "check", str(target), "--profile", "cis")
    assert result.output.count("cis") >= 1
    assert "annual" not in result.output


def test_a_profile_that_is_not_shipped_is_a_usage_error(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    target = tmp_path / "mystery.csv"
    target.write_text(CIS, encoding="utf-8")
    result = run("import", "check", str(target), "--profile", "wishful")
    assert result.exit_code == 2


def test_checking_writes_nothing_to_the_register(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    target = tmp_path / "mystery.csv"
    target.write_text(CIS, encoding="utf-8")
    run("import", "check", str(target))
    assert "nothing has been loaded" in run("import", "runs").output


def test_a_file_that_is_not_there_is_a_usage_error(run: Callable[..., Result]) -> None:
    assert run("import", "check", "/nowhere/at/all.csv").exit_code == 2
