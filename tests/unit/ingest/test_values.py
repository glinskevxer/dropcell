from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import IngestError
from dropcell.ingest.mapping import FieldType
from dropcell.ingest.values import coerce, parse_date, parse_flag
from dropcell.stationing import Convention, Station


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2025-03-14", dt.date(2025, 3, 14)),
        ("2025/03/14", dt.date(2025, 3, 14)),
        ("14-Mar-2025", dt.date(2025, 3, 14)),
        ("14 Mar 2025", dt.date(2025, 3, 14)),
        ("20250314", dt.date(2025, 3, 14)),
        ("  2025-03-14  ", dt.date(2025, 3, 14)),
    ],
)
def test_unambiguous_dates_are_read(text: str, expected: dt.date) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize("text", ["03/14/25", "14/03/2025", "3-14-25", "next tuesday", ""])
def test_an_ambiguous_or_broken_date_is_refused_rather_than_guessed(text: str) -> None:
    with pytest.raises(IngestError):
        parse_date(text)


def test_the_date_error_lists_what_it_would_have_taken() -> None:
    with pytest.raises(IngestError) as caught:
        parse_date("14/03/2025")
    assert "%Y-%m-%d" in caught.value.detail["accepted"]


@pytest.mark.parametrize("text", ["y", "Yes", "TRUE", "1", "x", " on "])
def test_the_many_spellings_of_yes(text: str) -> None:
    assert parse_flag(text) is True


@pytest.mark.parametrize("text", ["n", "No", "FALSE", "0", "off", "", "  "])
def test_the_many_spellings_of_no(text: str) -> None:
    assert parse_flag(text) is False


def test_something_that_is_neither_is_refused() -> None:
    with pytest.raises(IngestError):
        parse_flag("maybe")


def test_a_blank_cell_is_nothing_rather_than_zero() -> None:
    assert coerce("", FieldType.POTENTIAL) is None
    assert coerce("   ", FieldType.NUMBER) is None
    assert coerce("", FieldType.DATE) is None


def test_a_blank_flag_is_still_a_no() -> None:
    assert coerce("", FieldType.FLAG) is False


def test_a_potential_comes_back_in_millivolts() -> None:
    assert coerce("-0.912 V", FieldType.POTENTIAL) == pytest.approx(-912.0)
    assert coerce("-912", FieldType.POTENTIAL) == pytest.approx(-912.0)


def test_a_voltage_column_comes_back_in_volts() -> None:
    assert coerce("18.5 V", FieldType.VOLTAGE) == pytest.approx(18.5)
    assert coerce("1200 mV", FieldType.VOLTAGE) == pytest.approx(1.2)


def test_a_bare_number_in_a_voltage_column_is_volts_not_millivolts() -> None:
    assert coerce("18.5", FieldType.VOLTAGE) == pytest.approx(18.5)
    assert coerce("18.5", FieldType.POTENTIAL) == pytest.approx(18.5)


def test_a_station_is_read_in_the_convention_it_was_given() -> None:
    assert coerce("12+45.50", FieldType.STATION) == Station.parse("12+45.50")
    metric = coerce("1+000.0", FieldType.STATION, convention=Convention.METRIC)
    assert metric == Station(1000.0)


def test_lengths_currents_and_resistivities_land_on_their_canonical_units() -> None:
    assert coerce("100 ft", FieldType.LENGTH) == pytest.approx(30.48)
    assert coerce("250 mA", FieldType.CURRENT) == pytest.approx(0.25)
    assert coerce("4500", FieldType.RESISTIVITY) == pytest.approx(45.0)


def test_numbers_tolerate_thousands_separators() -> None:
    assert coerce("1,200", FieldType.INTEGER) == 1200
    assert coerce("18,500.5", FieldType.NUMBER) == pytest.approx(18500.5)


def test_text_comes_back_trimmed_and_otherwise_untouched() -> None:
    assert coerce("  R Ellis  ", FieldType.TEXT) == "R Ellis"


def test_a_cell_that_does_not_hold_what_its_column_says_is_refused() -> None:
    with pytest.raises(IngestError) as caught:
        coerce("not a number", FieldType.NUMBER)
    assert caught.value.detail["field_type"] == "number"
    assert "reason" in caught.value.detail


def test_a_broken_station_is_reported_against_its_column() -> None:
    with pytest.raises(IngestError) as caught:
        coerce("12+100.00", FieldType.STATION)
    assert caught.value.detail["field_type"] == "station"


def test_a_date_error_is_not_swallowed_and_relabelled() -> None:
    with pytest.raises(IngestError) as caught:
        coerce("14/03/2025", FieldType.DATE)
    assert "accepted" in caught.value.detail
