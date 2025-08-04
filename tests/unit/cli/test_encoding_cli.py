from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from click.testing import Result

ROWS = "Station,On,By\n0+00.00,-1120,{name}\n"


def test_a_utf8_file_says_so(run: Callable[..., Result], tmp_path: Path) -> None:
    target = tmp_path / "clean.csv"
    target.write_text(ROWS.format(name="R Ellis"), encoding="utf-8")
    result = run("import", "encoding", str(target))
    assert result.exit_code == 0
    assert "reads as utf-8" in result.output
    assert "spreadsheet" not in result.output


def test_a_file_with_a_byte_order_mark_says_so(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    target = tmp_path / "bom.csv"
    target.write_bytes(ROWS.format(name="R Ellis").encode("utf-8-sig"))
    result = run("import", "encoding", str(target))
    assert "utf-8-sig" in result.output
    assert "spreadsheet" not in result.output


def test_a_windows_export_is_named(run: Callable[..., Result], tmp_path: Path) -> None:
    target = tmp_path / "windows.csv"
    target.write_bytes(ROWS.format(name="José – relief").encode("cp1252"))
    result = run("import", "encoding", str(target))
    assert "cp1252" in result.output or "latin-1" in result.output
    assert "exported from a spreadsheet" in result.output


def test_a_file_that_is_not_there_is_a_usage_error(
    run: Callable[..., Result],
) -> None:
    assert run("import", "encoding", "/nowhere/at/all.csv").exit_code == 2
