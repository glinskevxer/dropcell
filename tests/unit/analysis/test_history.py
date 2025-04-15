from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.history import (
    as_of_year,
    best_by_year,
    compare_years,
    first_year,
    latest_pair,
    years_present,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.reading import Reading


def reading(
    code: str, year: int, off_mv: float | None, month: int = 5, lead: LeadKind = LeadKind.PIPE
) -> Reading:
    return Reading(
        test_point_code=code,
        lead=lead,
        taken_on=dt.date(year, month, 2),
        on_mv=-1120.0,
        off_mv=off_mv,
    )


def test_the_best_reading_of_a_year_is_the_most_protected_one() -> None:
    best = best_by_year([reading("TP-1", 2024, -800.0), reading("TP-1", 2024, -905.0, month=9)])
    assert best[("TP-1", 2024)].off_mv == pytest.approx(-905.0)


def test_a_reading_with_no_off_potential_does_not_count() -> None:
    assert best_by_year([reading("TP-1", 2024, None)]) == {}


def test_only_the_lead_asked_for_is_read() -> None:
    casing = reading("TP-1", 2024, -560.0, lead=LeadKind.CASING)
    assert best_by_year([casing]) == {}
    assert best_by_year([casing], lead=LeadKind.CASING)


def test_a_post_that_lost_criterion_is_named() -> None:
    result = compare_years(
        "AL-2",
        [reading("TP-1", 2023, -905.0), reading("TP-1", 2024, -800.0)],
        earlier_year=2023,
        later_year=2024,
    )
    assert [item.test_point_code for item in result.lost] == ["TP-1"]
    assert result.lost[0].movement_mv == pytest.approx(105.0)


def test_a_post_that_gained_criterion_is_named() -> None:
    result = compare_years(
        "AL-2",
        [reading("TP-1", 2023, -800.0), reading("TP-1", 2024, -905.0)],
        earlier_year=2023,
        later_year=2024,
    )
    assert [item.test_point_code for item in result.gained] == ["TP-1"]
    assert result.net == 1


def test_a_post_that_held_is_neither() -> None:
    result = compare_years(
        "AL-2",
        [reading("TP-1", 2023, -905.0), reading("TP-1", 2024, -910.0)],
        earlier_year=2023,
        later_year=2024,
    )
    assert result.held == ("TP-1",)
    assert result.stable


def test_a_year_where_the_rate_is_unchanged_can_still_have_churn() -> None:
    readings = [
        reading("TP-1", 2023, -905.0),
        reading("TP-2", 2023, -800.0),
        reading("TP-1", 2024, -800.0),
        reading("TP-2", 2024, -905.0),
    ]
    result = compare_years("AL-2", readings, earlier_year=2023, later_year=2024)
    assert result.net == 0
    assert result.churn == 2
    assert not result.stable


def test_a_post_read_in_only_one_year_is_held_out() -> None:
    readings = [reading("TP-1", 2023, -905.0), reading("TP-2", 2024, -800.0)]
    result = compare_years("AL-2", readings, earlier_year=2023, later_year=2024)
    assert result.compared == ()
    assert result.only_earlier == ("TP-1",)
    assert result.only_later == ("TP-2",)
    assert result.stable


def test_the_threshold_decides_which_side_a_post_is_on() -> None:
    readings = [reading("TP-1", 2023, -960.0), reading("TP-1", 2024, -905.0)]
    ordinary = compare_years("AL-2", readings, earlier_year=2023, later_year=2024)
    assert ordinary.stable
    tight = compare_years(
        "AL-2", readings, earlier_year=2023, later_year=2024, threshold_mv=-950.0
    )
    assert [item.test_point_code for item in tight.lost] == ["TP-1"]


def test_the_biggest_loss_comes_first() -> None:
    readings = [
        reading("TP-1", 2023, -905.0),
        reading("TP-2", 2023, -905.0),
        reading("TP-1", 2024, -840.0),
        reading("TP-2", 2024, -700.0),
    ]
    result = compare_years("AL-2", readings, earlier_year=2023, later_year=2024)
    assert [item.test_point_code for item in result.lost] == ["TP-2", "TP-1"]


def test_the_years_have_to_be_the_right_way_round() -> None:
    with pytest.raises(ValidationError):
        compare_years("AL-2", [], earlier_year=2024, later_year=2023)
    with pytest.raises(ValidationError):
        compare_years("AL-2", [], earlier_year=2024, later_year=2024)


def test_the_summary_names_both_years_and_the_net() -> None:
    readings = [reading("TP-1", 2023, -905.0), reading("TP-1", 2024, -800.0)]
    text = compare_years("AL-2", readings, earlier_year=2023, later_year=2024).summary()
    assert "AL-2 2023 to 2024" in text
    assert "net -1" in text


def test_the_years_present_are_listed_oldest_first() -> None:
    readings = [reading("TP-1", 2024, -905.0), reading("TP-1", 2022, -905.0)]
    assert years_present(readings) == [2022, 2024]


def test_the_latest_pair_is_the_two_most_recent_years() -> None:
    readings = [reading("TP-1", year, -905.0) for year in (2021, 2023, 2024)]
    assert latest_pair(readings) == (2023, 2024)


def test_one_year_of_readings_has_no_pair() -> None:
    assert latest_pair([reading("TP-1", 2024, -905.0)]) is None
    assert latest_pair([]) is None


def test_a_year_can_be_pulled_out_on_its_own() -> None:
    readings = [reading("TP-1", 2023, -905.0), reading("TP-1", 2024, -905.0)]
    assert [item.taken_on.year for item in as_of_year(readings, 2024)] == [2024]


def test_the_first_year_is_the_earliest_reading() -> None:
    readings = [reading("TP-1", 2024, -905.0), reading("TP-1", 2021, None)]
    assert first_year(readings) == 2021
    assert first_year([]) is None
