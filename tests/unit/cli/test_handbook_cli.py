from __future__ import annotations

from collections.abc import Callable

from click.testing import Result


def test_the_whole_handbook_prints(run: Callable[..., Result]) -> None:
    result = run("handbook")
    assert result.exit_code == 0
    assert "Setting a register up" in result.output
    assert "What the exit codes mean" in result.output


def test_one_section_can_be_asked_for(run: Callable[..., Result]) -> None:
    result = run("handbook", "units")
    assert "Units and stationing" in result.output
    assert "Setting a register up" not in result.output


def test_the_section_names_can_be_listed(run: Callable[..., Result]) -> None:
    result = run("handbook", "list")
    assert "units" in result.output
    assert "exits" in result.output
    assert "----" not in result.output


def test_an_unknown_section_is_a_usage_error(run: Callable[..., Result]) -> None:
    result = run("handbook", "wishful")
    assert result.exit_code == 2
    assert "validation:" in result.output


def test_the_handbook_needs_no_register(run: Callable[..., Result]) -> None:
    result = run("handbook", "year")
    assert result.exit_code == 0
    assert "nothing has been loaded" not in result.output
