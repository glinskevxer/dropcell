from __future__ import annotations

import json
from collections.abc import Callable
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


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
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
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
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


@pytest.fixture
def other(tmp_path: Path) -> Callable[..., Result]:
    target = tmp_path / "other.sqlite"
    runner = CliRunner()

    def invoke(*args: str) -> Result:
        return runner.invoke(main, ["--register", str(target), "--today", "2025-03-14", *args])

    return invoke


def test_a_line_exports_to_standard_output(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("line", "export", "AL-2")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["line"]["code"] == "AL-2"
    assert len(payload["readings"]) == 1


def test_a_line_exports_to_a_file(run: Callable[..., Result], tmp_path: Path) -> None:
    seed(run)
    target = tmp_path / "al-2.json"
    result = run("line", "export", "AL-2", "--out", str(target))
    assert result.exit_code == 0
    assert "1 segments" in result.output
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["line"]["code"] == "AL-2"


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("line", "export", "ZZ-9").exit_code == 3


def test_a_document_lands_in_another_register(
    run: Callable[..., Result], other: Callable[..., Result], tmp_path: Path
) -> None:
    seed(run)
    target = tmp_path / "al-2.json"
    run("line", "export", "AL-2", "--out", str(target))
    imported = other("line", "import", str(target))
    assert imported.exit_code == 0
    assert "AL-2 imported" in imported.output
    assert "AL-2" in other("line", "list").output


def test_everything_arrives_with_the_line(
    run: Callable[..., Result], other: Callable[..., Result], tmp_path: Path
) -> None:
    seed(run)
    target = tmp_path / "al-2.json"
    run("line", "export", "AL-2", "--out", str(target))
    other("line", "import", str(target))
    assert "TP-1" in other("post", "list", "--line", "AL-2").output
    assert "-905" in other("post", "show", "TP-1").output
    assert "F-2025-001" in other("report", "exceptions").output


def test_the_same_line_twice_is_a_conflict(run: Callable[..., Result], tmp_path: Path) -> None:
    seed(run)
    target = tmp_path / "al-2.json"
    run("line", "export", "AL-2", "--out", str(target))
    assert run("line", "import", str(target)).exit_code == 4


def test_a_file_that_is_not_json_is_a_usage_error(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    target = tmp_path / "junk.json"
    target.write_text("this is not json", encoding="utf-8")
    result = run("line", "import", str(target))
    assert result.exit_code == 2
    assert "not readable JSON" in result.output


def test_a_json_document_that_is_a_list_is_a_usage_error(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    target = tmp_path / "list.json"
    target.write_text("[]", encoding="utf-8")
    assert run("line", "import", str(target)).exit_code == 2


def test_a_document_from_another_build_is_a_usage_error(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    seed(run)
    target = tmp_path / "al-2.json"
    run("line", "export", "AL-2", "--out", str(target))
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["version"] = 99
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert run("line", "import", str(target)).exit_code == 2


def test_a_file_that_is_not_there_is_a_usage_error(run: Callable[..., Result]) -> None:
    assert run("line", "import", "/nowhere/at/all.json").exit_code == 2
