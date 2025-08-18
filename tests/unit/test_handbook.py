from __future__ import annotations

import pytest

from dropcell.errors import ValidationError
from dropcell.handbook import SECTIONS, keys, render, section


def test_every_section_has_a_key_a_title_and_a_body() -> None:
    for item in SECTIONS:
        assert item.key
        assert item.title
        assert item.body.strip()


def test_the_keys_are_unique() -> None:
    assert len(keys()) == len(set(keys()))


def test_a_section_can_be_fetched_by_name() -> None:
    assert section("units").title == "Units and stationing"


def test_an_unknown_section_lists_the_ones_that_exist() -> None:
    with pytest.raises(ValidationError) as caught:
        section("wishful")
    assert "units" in caught.value.detail["known"]


def test_a_rendered_section_carries_its_heading() -> None:
    text = section("exits").render()
    assert text.startswith("What the exit codes mean\n---")


def test_rendering_everything_carries_every_section() -> None:
    text = render()
    for item in SECTIONS:
        assert item.title in text


def test_rendering_one_section_carries_only_that_one() -> None:
    text = render("units")
    assert "Units and stationing" in text
    assert "What the exit codes mean" not in text


def test_the_exit_codes_in_the_handbook_match_the_code() -> None:
    from dropcell.cli.context import EXIT_CONFLICT, EXIT_NOT_FOUND, EXIT_USAGE

    text = section("exits").body
    assert f"{EXIT_USAGE}   the command was wrong" in text
    assert f"{EXIT_NOT_FOUND}   something named on the command line" in text
    assert f"{EXIT_CONFLICT}   the register refused the write" in text


def test_the_groups_section_names_every_command_group() -> None:
    from dropcell.cli.main import main

    text = section("groups").body
    for name in main.commands:
        assert name in text, name


def test_the_handbook_does_not_explain_the_domain() -> None:
    text = render().lower()
    assert "copper sulfate" not in text
    assert "half cell" not in text
