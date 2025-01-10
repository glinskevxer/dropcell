from __future__ import annotations

from pathlib import Path

import pytest

from dropcell.config import Settings, find, from_mapping, known_keys, load, load_or_default
from dropcell.errors import ValidationError


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_the_defaults_match_what_the_code_already_did() -> None:
    settings = Settings()
    assert settings.protection_mv == pytest.approx(-850.0)
    assert settings.decay_mv == pytest.approx(100.0)
    assert settings.post_reach_m == pytest.approx(1600.0)
    assert settings.dig_budget is None


def test_a_positive_criterion_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(protection_mv=850.0)


def test_an_over_protection_limit_above_the_criterion_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(protection_mv=-850.0, over_protection_mv=-800.0)


def test_a_non_positive_decay_criterion_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(decay_mv=0.0)


def test_ac_bands_that_are_the_wrong_way_round_are_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(ac_low_risk_a_per_m2=100.0, ac_high_risk_a_per_m2=30.0)


def test_a_reach_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(post_reach_m=0.0)


def test_a_negative_dig_budget_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(dig_budget=-1)


def test_a_setting_this_build_does_not_know_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        from_mapping({"protecton_mv": -850.0})
    assert caught.value.detail["unknown"] == ["protecton_mv"]
    assert "protection_mv" in caught.value.detail["known"]


def test_every_field_is_a_known_key() -> None:
    assert "register" in known_keys()
    assert "dig_budget" in known_keys()


def test_a_file_can_carry_a_bare_table(tmp_path: Path) -> None:
    target = write(
        tmp_path / "dropcell.toml", 'operator = "Northmoor Gas"\nprotection_mv = -950\n'
    )
    settings = load(target)
    assert settings.operator == "Northmoor Gas"
    assert settings.protection_mv == pytest.approx(-950.0)


def test_a_file_can_carry_a_dropcell_section(tmp_path: Path) -> None:
    target = write(
        tmp_path / "dropcell.toml",
        '[dropcell]\noperator = "Northmoor Gas"\npost_reach_m = 400\n',
    )
    assert load(target).post_reach_m == pytest.approx(400.0)


def test_settings_the_file_does_not_carry_keep_their_defaults(tmp_path: Path) -> None:
    target = write(tmp_path / "dropcell.toml", 'operator = "Northmoor Gas"\n')
    assert load(target).protection_mv == pytest.approx(-850.0)


def test_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load(tmp_path / "nowhere.toml")


def test_a_file_that_is_not_toml_is_refused(tmp_path: Path) -> None:
    target = write(tmp_path / "dropcell.toml", "this is not toml = = =\n")
    with pytest.raises(ValidationError) as caught:
        load(target)
    assert "reason" in caught.value.detail


def test_a_dropcell_key_that_is_not_a_table_is_refused(tmp_path: Path) -> None:
    target = write(tmp_path / "dropcell.toml", 'dropcell = "nope"\n')
    with pytest.raises(ValidationError):
        load(target)


def test_a_file_with_a_bad_value_is_refused(tmp_path: Path) -> None:
    target = write(tmp_path / "dropcell.toml", "protection_mv = 850\n")
    with pytest.raises(ValidationError):
        load(target)


def test_the_search_finds_a_file_beside_the_starting_point(tmp_path: Path) -> None:
    write(tmp_path / "dropcell.toml", 'operator = "x"\n')
    assert find(tmp_path) == tmp_path / "dropcell.toml"


def test_the_search_walks_up_the_tree(tmp_path: Path) -> None:
    write(tmp_path / "dropcell.toml", 'operator = "x"\n')
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert find(deep) == tmp_path / "dropcell.toml"


def test_the_hidden_name_is_found_too(tmp_path: Path) -> None:
    write(tmp_path / ".dropcell.toml", 'operator = "x"\n')
    assert find(tmp_path) == tmp_path / ".dropcell.toml"


def test_the_plain_name_wins_over_the_hidden_one(tmp_path: Path) -> None:
    write(tmp_path / "dropcell.toml", 'operator = "plain"\n')
    write(tmp_path / ".dropcell.toml", 'operator = "hidden"\n')
    found = find(tmp_path)
    assert found is not None
    assert load(found).operator == "plain"


def test_a_named_file_beats_the_search(tmp_path: Path) -> None:
    write(tmp_path / "dropcell.toml", 'operator = "found"\n')
    named = write(tmp_path / "other.toml", 'operator = "named"\n')
    assert load_or_default(named, start=tmp_path).operator == "named"


def test_the_nearest_file_is_used_when_none_is_named(tmp_path: Path) -> None:
    write(tmp_path / "dropcell.toml", 'operator = "found"\n')
    assert load_or_default(start=tmp_path).operator == "found"


def test_no_file_anywhere_gives_the_defaults(tmp_path: Path) -> None:
    deep = tmp_path / "a"
    deep.mkdir()
    settings = load_or_default(start=deep)
    assert settings.operator == ""
