from __future__ import annotations

from pathlib import Path

import pytest

from dropcell.config import Settings, load, parse_profile
from dropcell.errors import ValidationError
from dropcell.ingest.mapping import FieldType
from dropcell.ingest.reader import read_text

TOML = """
operator = "Northmoor Gas"

[[profiles]]
name = "beckside"
description = "the file Beckside Surveys send"
skip_rows = 1

  [[profiles.columns]]
  field = "station"
  type = "station"
  headers = ["POS", "Position"]

  [[profiles.columns]]
  field = "on_mv"
  type = "potential"
  headers = ["VON"]

  [[profiles.columns]]
  field = "off_mv"
  type = "potential"
  headers = ["VOFF"]
  required = false
"""


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_a_settings_file_can_add_a_profile(tmp_path: Path) -> None:
    settings = load(write(tmp_path / "dropcell.toml", TOML))
    assert [item.name for item in settings.profiles] == ["beckside"]
    assert settings.profile("beckside") is not None
    assert settings.profile("nothing") is None


def test_the_added_profile_reads_its_contractor_file(tmp_path: Path) -> None:
    settings = load(write(tmp_path / "dropcell.toml", TOML))
    profile = settings.profile("beckside")
    assert profile is not None
    text = "Beckside Surveys Ltd\nPOS,VON,VOFF\n0+00.00,-1120,-905\n"
    result = read_text(text, profile)
    assert result.accepted == 1
    assert result.rows[0]["off_mv"] == pytest.approx(-905.0)


def test_the_added_profile_takes_the_aliases_it_was_given(tmp_path: Path) -> None:
    settings = load(write(tmp_path / "dropcell.toml", TOML))
    profile = settings.profile("beckside")
    assert profile is not None
    text = "Beckside Surveys Ltd\nPosition,VON\n0+00.00,-1120\n"
    assert read_text(text, profile).accepted == 1


def test_an_optional_column_stays_optional(tmp_path: Path) -> None:
    settings = load(write(tmp_path / "dropcell.toml", TOML))
    profile = settings.profile("beckside")
    assert profile is not None
    text = "Beckside Surveys Ltd\nPOS,VON\n0+00.00,-1120\n"
    assert read_text(text, profile).rows[0]["off_mv"] is None


def test_a_profile_with_no_name_is_refused() -> None:
    with pytest.raises(ValidationError):
        parse_profile({"columns": []})


def test_a_profile_with_no_columns_is_refused() -> None:
    with pytest.raises(ValidationError):
        parse_profile({"name": "x"})


def test_columns_that_are_not_a_list_are_refused() -> None:
    with pytest.raises(ValidationError):
        parse_profile({"name": "x", "columns": "nope"})


def test_a_column_that_is_not_a_table_is_refused() -> None:
    with pytest.raises(ValidationError):
        parse_profile({"name": "x", "columns": ["nope"]})


def test_a_column_type_this_build_does_not_know_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        parse_profile(
            {"name": "x", "columns": [{"field": "a", "type": "wishful", "headers": ["A"]}]}
        )
    assert "text" in caught.value.detail["known"]


def test_a_column_key_this_build_ignores_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        parse_profile(
            {"name": "x", "columns": [{"field": "a", "headers": ["A"], "colour": "red"}]}
        )
    assert caught.value.detail["unknown"] == ["colour"]


def test_a_column_with_no_type_is_read_as_text() -> None:
    profile = parse_profile({"name": "x", "columns": [{"field": "a", "headers": ["A"]}]})
    assert profile.columns[0].field_type is FieldType.TEXT


def test_two_profiles_with_one_name_are_refused() -> None:
    profile = parse_profile({"name": "x", "columns": [{"field": "a", "headers": ["A"]}]})
    with pytest.raises(ValidationError):
        Settings(profiles=(profile, profile))


def test_profiles_that_are_not_a_list_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load(write(tmp_path / "dropcell.toml", 'profiles = "nope"\n'))


def test_a_settings_file_with_no_profiles_has_none(tmp_path: Path) -> None:
    assert load(write(tmp_path / "dropcell.toml", 'operator = "x"\n')).profiles == ()
