from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import click
import pytest
from click.testing import CliRunner, Result

from dropcell.cli.context import handled, wants_traceback
from dropcell.cli.main import main
from dropcell.errors import NotFoundError


@pytest.fixture
def bare(register: Path) -> Callable[..., Result]:
    runner = CliRunner()

    def invoke(*args: str) -> Result:
        argv: Sequence[str] = ["--register", str(register), *args]
        return runner.invoke(main, list(argv))

    return invoke


def test_without_the_flag_an_error_is_a_message_and_a_code(
    bare: Callable[..., Result],
) -> None:
    result = bare("line", "show", "ZZ-9")
    assert result.exit_code == 3
    assert "not_found:" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_with_the_flag_the_exception_escapes(bare: Callable[..., Result]) -> None:
    result = bare("--traceback", "line", "show", "ZZ-9")
    assert isinstance(result.exception, NotFoundError)


def test_the_flag_does_not_change_a_working_command(
    bare: Callable[..., Result],
) -> None:
    assert bare("--traceback", "init").exit_code == 0


def test_the_flag_reaches_a_command_nested_in_a_group(
    bare: Callable[..., Result],
) -> None:
    result = bare("--traceback", "report", "protection", "--line", "ZZ-9")
    assert isinstance(result.exception, NotFoundError)


def test_the_helper_says_no_when_nothing_is_asking() -> None:
    assert not wants_traceback()


def test_a_decorated_command_with_no_context_still_handles_errors() -> None:
    @click.command()
    @handled
    def command() -> None:
        raise NotFoundError("nothing here", code="X")

    result = CliRunner().invoke(command)
    assert result.exit_code == 3
    assert "not_found: nothing here" in result.output


def test_an_error_that_is_not_ours_is_never_swallowed() -> None:
    @click.command()
    @handled
    def command() -> None:
        raise RuntimeError("something else")

    result = CliRunner().invoke(command)
    assert isinstance(result.exception, RuntimeError)
