from __future__ import annotations

import pytest

from dropcell.errors import ValidationError
from dropcell.model.ids import MAX_CODE_LENGTH, is_code, normalise_code, normalise_post_number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("al-2", "AL-2"),
        ("  AL-2  ", "AL-2"),
        ("al 2", "AL-2"),
        ("al_2", "AL-2"),
        ("AL--2", "AL-2"),
        ("-AL-2-", "AL-2"),
        ("al–2", "AL-2"),
        ("TP-114A", "TP-114A"),
    ],
)
def test_field_written_codes_fold_onto_one_form(raw: str, expected: str) -> None:
    assert normalise_code(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "---", "AL/2", "AL.2", "AL 2!", "é"])
def test_a_code_that_cannot_be_saved_is_refused(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalise_code(raw)


def test_a_code_past_the_length_limit_is_refused_with_the_limit_named() -> None:
    with pytest.raises(ValidationError) as caught:
        normalise_code("A" * (MAX_CODE_LENGTH + 1))
    assert caught.value.detail["limit"] == MAX_CODE_LENGTH


def test_a_code_exactly_at_the_limit_is_accepted() -> None:
    assert normalise_code("A" * MAX_CODE_LENGTH) == "A" * MAX_CODE_LENGTH


def test_the_error_names_the_kind_it_was_asked_for() -> None:
    with pytest.raises(ValidationError) as caught:
        normalise_code("  ", kind="rectifier tag")
    assert "rectifier tag" in caught.value.message


def test_a_non_string_code_is_refused() -> None:
    with pytest.raises(ValidationError):
        normalise_code(114)  # type: ignore[arg-type]


def test_a_numeric_post_number_loses_its_leading_zeros() -> None:
    assert normalise_post_number("007") == "7"
    assert normalise_post_number("0") == "0"


def test_a_post_number_with_a_letter_keeps_its_shape() -> None:
    assert normalise_post_number("07a") == "07A"


def test_is_code_only_accepts_the_already_canonical_form() -> None:
    assert is_code("AL-2")
    assert not is_code("al-2")
    assert not is_code(" AL-2")
    assert not is_code("")
