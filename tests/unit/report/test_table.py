from __future__ import annotations

import pytest

from dropcell.errors import ValidationError
from dropcell.report.table import Column, Table, truncate


def simple() -> Table:
    return Table(
        columns=(
            Column("code", "Post"),
            Column("off", "Off mV", align="right", format=".0f"),
        )
    )


def test_an_empty_table_says_so() -> None:
    assert simple().render() == "nothing to report"


def test_an_empty_table_can_say_something_else() -> None:
    table = Table(columns=(Column("a", "A"),), empty_note="no findings")
    assert table.render() == "no findings"


def test_a_title_sits_above_the_table() -> None:
    table = Table(columns=(Column("a", "A"),), title="Exceptions")
    assert table.render().startswith("Exceptions\n\n")


def test_a_one_row_table_renders_a_header_a_rule_and_the_row() -> None:
    lines = simple().add(code="TP-114", off=-905.0).render().splitlines()
    assert lines[0] == "Post    Off mV"
    assert lines[1] == "------  ------"
    assert lines[2] == "TP-114    -905"


def test_columns_widen_to_the_longest_value() -> None:
    table = simple().add(code="TP-114", off=-905.0).add(code="TP-1140000", off=-1.0)
    assert table.render().splitlines()[0].startswith("Post      ")


def test_numbers_are_right_aligned_and_text_is_left_aligned() -> None:
    lines = simple().add(code="TP-1", off=-905.0).render().splitlines()
    assert lines[2] == "TP-1    -905"
    assert lines[2].endswith("-905")
    assert lines[2].startswith("TP-1")


def test_a_format_string_is_applied_to_the_value() -> None:
    table = Table(columns=(Column("share", "Share", align="right", format=".1%"),))
    assert table.add(share=0.4567).render().splitlines()[2].strip() == "45.7%"


def test_a_missing_value_renders_as_nothing() -> None:
    lines = simple().add(code="TP-1").render().splitlines()
    assert lines[2].rstrip() == "TP-1"


def test_a_none_value_renders_as_nothing_even_with_a_format() -> None:
    lines = simple().add(code="TP-1", off=None).render().splitlines()
    assert lines[2].rstrip() == "TP-1"


def test_long_text_is_shortened_at_the_column_width() -> None:
    table = Table(columns=(Column("note", "Note", width=8),))
    rendered = table.add(note="sixty metres under criterion").render()
    assert "…" in rendered
    assert max(len(line) for line in rendered.splitlines()) == 8


def test_a_number_is_never_shortened_even_past_the_width() -> None:
    table = Table(columns=(Column("n", "N", align="right", width=3),))
    rendered = table.add(n=-1234567).render()
    assert "-1234567" in rendered


def test_truncation_marks_that_it_happened() -> None:
    assert truncate("abcdef", 10) == "abcdef"
    assert truncate("abcdef", 6) == "abcdef"
    assert truncate("abcdef", 4) == "abc…"
    assert truncate("abcdef", 1) == "…"


def test_truncating_to_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        truncate("abc", 0)


def test_a_column_aligned_anywhere_else_is_refused() -> None:
    with pytest.raises(ValidationError):
        Column("a", "A", align="centre")


def test_a_column_width_below_one_is_refused() -> None:
    with pytest.raises(ValidationError):
        Column("a", "A", width=0)


def test_rows_can_be_added_in_bulk() -> None:
    table = simple().extend([{"code": "TP-1", "off": -905.0}, {"code": "TP-2", "off": -880.0}])
    assert len(table.render().splitlines()) == 4


def test_adding_returns_the_table_so_calls_chain() -> None:
    table = simple().add(code="TP-1", off=-905.0).add(code="TP-2", off=-880.0)
    assert len(table.rows) == 2


def test_no_line_carries_trailing_whitespace() -> None:
    table = Table(columns=(Column("a", "A"), Column("b", "Bbbbbbbb")))
    rendered = table.add(a="x", b="y").render()
    assert all(line == line.rstrip() for line in rendered.splitlines())


def test_the_table_stringifies_to_its_rendering() -> None:
    table = simple().add(code="TP-1", off=-905.0)
    assert str(table) == table.render()
