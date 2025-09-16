"""What one point oh promises, held where it can be checked.

A version number is a claim about what will not change. The claim is worth
nothing unless the things it covers are named somewhere a test can read them,
which is what this suite does: the public list, the exit codes, the transfer
format and the JSON shape.

Everything else in the package is free to change on any Tuesday, and that is
deliberate. A promise about the whole of a codebase is a promise nobody can keep.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

import dropcell
from dropcell.cli.context import EXIT_CONFLICT, EXIT_NOT_FOUND, EXIT_USAGE
from dropcell.cli.main import main
from dropcell.store.transfer import FORMAT, FORMAT_VERSION

ROOT = Path(__file__).resolve().parents[2]


def test_the_version_is_one_point_oh() -> None:
    assert dropcell.__version__ == "1.0.0"


def test_the_package_and_the_project_file_agree() -> None:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert payload["project"]["version"] == dropcell.__version__


def test_the_changelog_names_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {dropcell.__version__}" in text


def test_the_changelog_says_what_the_promise_covers() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for covered in ("__all__", "exit codes", "transfer document", "JSON"):
        assert covered in text


def test_the_exit_codes_are_the_ones_the_handbook_publishes() -> None:
    assert (EXIT_USAGE, EXIT_NOT_FOUND, EXIT_CONFLICT) == (2, 3, 4)


def test_the_transfer_format_is_named_and_versioned() -> None:
    assert FORMAT == "dropcell-line-transfer"
    assert FORMAT_VERSION == 1


def test_the_public_list_is_not_empty_and_imports() -> None:
    assert len(dropcell.__all__) > 30
    for name in dropcell.__all__:
        assert hasattr(dropcell, name)


@pytest.fixture
def runner(tmp_path: Path) -> CliRunner:
    return CliRunner()


def test_about_emits_json_a_script_can_read(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, ["--register", str(tmp_path / "cp.sqlite"), "about", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["version"] == dropcell.__version__
    assert payload["register_exists"] is False
    assert payload["schema_version"] >= 15


def test_about_json_carries_the_thresholds(runner: CliRunner, tmp_path: Path) -> None:
    config = tmp_path / "dropcell.toml"
    config.write_text("protection_mv = -950\n", encoding="utf-8")
    result = runner.invoke(
        main,
        [
            "--register",
            str(tmp_path / "cp.sqlite"),
            "--config",
            str(config),
            "about",
            "--json",
        ],
    )
    payload = json.loads(result.output)
    assert payload["protection_mv"] == -950.0


def test_about_json_counts_a_register_that_is_there(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "cp.sqlite"
    runner.invoke(main, ["--register", str(target), "init"])
    result = runner.invoke(main, ["--register", str(target), "about", "--json"])
    payload = json.loads(result.output)
    assert payload["register_exists"] is True
    assert payload["rows"]["line"] == 0


def test_the_version_option_prints_the_same_number(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])
    assert dropcell.__version__ in result.output


def test_the_readme_and_the_handbook_agree_on_the_command_name() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "dropcell handbook" in readme
    assert "dropcell --help" in readme
