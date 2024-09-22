from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from dropcell import __version__
from dropcell.cli.context import (
    EXIT_CONFLICT,
    EXIT_NOT_FOUND,
    EXIT_USAGE,
    Context,
    exit_code_for,
)
from dropcell.cli.main import main
from dropcell.errors import (
    ConflictError,
    DropcellError,
    IngestError,
    MigrationError,
    NotFoundError,
    StoreError,
    UnitError,
    ValidationError,
)
from dropcell.store.migrations import latest_version


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_the_help_names_the_domain(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "buried steel pipelines" in result.output


def test_the_version_is_the_package_version(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])
    assert __version__ in result.output


def test_init_creates_a_register(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "cp.sqlite"
    result = runner.invoke(main, ["--register", str(target), "init"])
    assert result.exit_code == 0
    assert target.exists()
    assert f"schema version {latest_version()}" in result.output


def test_init_on_an_existing_register_is_harmless(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "cp.sqlite"
    runner.invoke(main, ["--register", str(target), "init"])
    result = runner.invoke(main, ["--register", str(target), "init"])
    assert result.exit_code == 0


def test_the_register_path_can_come_from_the_environment(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "from-env.sqlite"
    result = runner.invoke(main, ["init"], env={"DROPCELL_REGISTER": str(target)})
    assert result.exit_code == 0
    assert target.exists()


def test_schema_lists_every_migration(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "cp.sqlite"
    result = runner.invoke(main, ["--register", str(target), "schema"])
    assert result.exit_code == 0
    assert result.output.count("applied") == latest_version()
    assert "pending" not in result.output


def test_a_register_in_a_directory_that_is_not_there_fails_cleanly(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "nowhere" / "cp.sqlite"
    result = runner.invoke(main, ["--register", str(target), "init"])
    assert result.exit_code != 0
    assert "store:" in result.output


def test_a_bad_today_is_a_usage_error(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        main, ["--register", str(tmp_path / "cp.sqlite"), "--today", "nonsense", "init"]
    )
    assert result.exit_code != 0


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ValidationError("x"), EXIT_USAGE),
        (UnitError("x"), EXIT_USAGE),
        (IngestError("x"), EXIT_USAGE),
        (NotFoundError("x"), EXIT_NOT_FOUND),
        (ConflictError("x"), EXIT_CONFLICT),
        (StoreError("x"), 1),
        (MigrationError("x"), 1),
        (DropcellError("x"), 1),
    ],
)
def test_each_error_maps_to_its_own_exit_code(error: DropcellError, code: int) -> None:
    assert exit_code_for(error) == code


def test_the_context_opens_the_register_only_once(tmp_path: Path) -> None:
    import datetime as dt

    context = Context(register_path=str(tmp_path / "cp.sqlite"), today=dt.date(2025, 3, 14))
    first = context.database()
    assert context.database() is first
    context.close()
    assert context.database() is not first
    context.close()


def test_closing_a_context_that_never_opened_anything_is_fine(tmp_path: Path) -> None:
    import datetime as dt

    Context(register_path=str(tmp_path / "cp.sqlite"), today=dt.date(2025, 3, 14)).close()
