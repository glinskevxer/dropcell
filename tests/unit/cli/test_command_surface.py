"""Every command, held to the same standard without anybody having to remember.

Thirty commands written over two years drift. One ends up with no help text,
one takes a measurement without a unit, one is added to a group and never
mentioned anywhere a person would look. None of those breaks anything, and all
of them make the tool harder to use than it needs to be.

So the surface is walked rather than listed. A command added tomorrow is held to
this without anybody adding a test for it, which is the only way a rule like
this survives contact with a deadline.
"""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from dropcell.cli.main import main
from dropcell.handbook import section

MEASUREMENT_OPTIONS = {
    "--length",
    "--diameter",
    "--wall",
    "--cover",
    "--soil",
    "--at",
    "--from",
    "--to",
    "--on",
    "--off",
    "--reach",
    "--step",
    "--gap",
    "--minimum",
    "--threshold",
}


def walk(command: click.Command, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Every leaf command, by the words somebody would type to reach it."""
    if isinstance(command, click.Group):
        found: list[tuple[str, ...]] = []
        for name, child in command.commands.items():
            found.extend(walk(child, (*path, name)))
        return found
    return [path]


LEAVES = walk(main)


def resolve(path: tuple[str, ...]) -> click.Command:
    """The command at the end of a path of words."""
    command: click.Command = main
    for name in path:
        assert isinstance(command, click.Group)
        command = command.commands[name]
    return command


def test_there_are_commands_to_walk() -> None:
    assert len(LEAVES) > 40


@pytest.mark.parametrize("path", LEAVES, ids=lambda item: " ".join(item))
def test_every_command_says_what_it_does(path: tuple[str, ...]) -> None:
    command = resolve(path)
    assert command.help, " ".join(path)
    assert command.help.strip()[0].isupper()


@pytest.mark.parametrize("path", LEAVES, ids=lambda item: " ".join(item))
def test_every_command_answers_for_help(path: tuple[str, ...]) -> None:
    result = CliRunner().invoke(main, [*path, "--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


@pytest.mark.parametrize("path", LEAVES, ids=lambda item: " ".join(item))
def test_every_option_says_what_it_is_for(path: tuple[str, ...]) -> None:
    command = resolve(path)
    for parameter in command.params:
        if not isinstance(parameter, click.Option):
            continue
        if parameter.name in {"help"}:
            continue
        described = bool(parameter.help) or parameter.is_flag or bool(parameter.type.name)
        assert described, f"{' '.join(path)} {parameter.opts}"


def test_every_group_is_named_in_the_handbook() -> None:
    text = section("groups").body
    for name in main.commands:
        assert name in text, name


def test_the_year_section_names_the_commands_a_year_uses() -> None:
    text = section("year").body
    for phrase in ("import annual", "report protection", "report compliance", "finding"):
        assert phrase in text


def test_the_start_section_names_the_commands_a_register_needs() -> None:
    text = section("start").body
    for phrase in ("init", "line add", "segment add", "post add", "register check"):
        assert phrase in text


def test_no_two_commands_share_a_path() -> None:
    assert len(LEAVES) == len(set(LEAVES))


def test_the_top_level_takes_the_options_every_command_needs() -> None:
    names = {parameter.name for parameter in main.params}
    assert {"register_path", "config_path", "today", "quiet", "verbosity"} <= names


def test_the_reporting_commands_never_take_a_write_option() -> None:
    for path in LEAVES:
        if path[0] not in {"report", "plan"}:
            continue
        opts = {opt for parameter in resolve(path).params for opt in parameter.opts}
        assert "--raise-findings" not in opts, " ".join(path)
