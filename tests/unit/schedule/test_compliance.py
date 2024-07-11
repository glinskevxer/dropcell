from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.schedule.compliance import evaluate_rule
from dropcell.schedule.policy import RECTIFIER_BIMONTHLY, TEST_POINT_ANNUAL


def day(year: int, month: int, number: int) -> dt.date:
    return dt.date(year, month, number)


def annual(visits: list[dt.date], as_of: dt.date, **kwargs: object):  # type: ignore[no-untyped-def]
    return evaluate_rule(
        TEST_POINT_ANNUAL,
        visits,
        asset_code="TP-114",
        as_of=as_of,
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_tidy_annual_history_is_compliant() -> None:
    visits = [day(2022, 5, 2), day(2023, 5, 8), day(2024, 4, 30), day(2025, 5, 6)]
    result = annual(visits, day(2025, 6, 1))
    assert result.compliant
    assert result.reasons() == ()


def test_six_visits_crammed_into_december_break_the_interval() -> None:
    visits = [day(2024, 12, index) for index in (1, 2, 3, 4, 5, 6)]
    result = evaluate_rule(
        RECTIFIER_BIMONTHLY,
        visits,
        asset_code="RU-3",
        as_of=day(2025, 1, 5),
        in_service_from=day(2024, 1, 1),
    )
    assert [year.year for year in result.year_counts] == [2024]
    assert result.year_counts[0].met
    assert not result.compliant
    assert any("days against a limit" in reason for reason in result.reasons())


def test_a_visit_every_fourteen_months_misses_a_calendar_year() -> None:
    visits = [day(2022, 1, 10), day(2023, 3, 10), day(2024, 5, 10), day(2025, 7, 10)]
    result = annual(visits, day(2025, 12, 1))
    assert result.breaches == ()
    assert [year.year for year in result.short_years] == []
    longer = annual([day(2022, 1, 10), day(2023, 3, 10), day(2025, 2, 1)], day(2025, 12, 1))
    assert [year.year for year in longer.short_years] == [2024]


def test_the_year_in_progress_is_never_reported_as_short() -> None:
    result = annual([day(2024, 5, 2)], day(2025, 1, 3))
    assert [year.year for year in result.year_counts] == [2024]
    assert result.compliant


def test_a_gap_from_the_last_visit_to_today_is_still_a_gap() -> None:
    result = annual([day(2023, 5, 2)], day(2025, 3, 14))
    breach = result.open_breach
    assert breach is not None
    assert breach.still_open
    assert breach.following is None
    assert breach.days == (day(2025, 3, 14) - day(2023, 5, 2)).days
    assert not result.compliant


def test_an_open_gap_inside_the_limit_is_not_a_breach() -> None:
    result = annual([day(2024, 5, 2)], day(2025, 3, 14))
    assert result.open_breach is None


def test_a_breach_reports_how_far_past_the_limit_it_ran() -> None:
    result = annual([day(2023, 1, 1), day(2024, 6, 1)], day(2024, 7, 1))
    breach = result.breaches[0]
    assert breach.days == 517
    assert breach.over_by_days == 517 - TEST_POINT_ANNUAL.maximum_interval_days
    assert not breach.still_open


def test_the_next_due_date_comes_off_the_last_visit() -> None:
    result = annual([day(2024, 5, 2)], day(2025, 3, 14))
    assert result.next_due == dt.date(2025, 8, 1)
    assert result.days_until_due == (dt.date(2025, 8, 1) - dt.date(2025, 3, 14)).days
    assert not result.overdue


def test_an_asset_past_its_due_date_says_so() -> None:
    result = annual([day(2023, 5, 2)], day(2025, 3, 14))
    assert result.overdue
    assert result.days_until_due is not None
    assert result.days_until_due < 0


def test_an_asset_never_visited_dates_from_when_it_went_in() -> None:
    result = annual([], day(2025, 3, 14), in_service_from=day(2023, 1, 1))
    assert result.visits == ()
    assert result.next_due == TEST_POINT_ANNUAL.next_due(day(2023, 1, 1))
    assert result.open_breach is not None
    assert [year.year for year in result.short_years] == [2023, 2024]


def test_an_asset_with_no_history_and_no_service_date_says_nothing() -> None:
    result = annual([], day(2025, 3, 14))
    assert result.year_counts == ()
    assert result.breaches == ()
    assert result.next_due is None
    assert result.days_until_due is None
    assert result.compliant


def test_duplicate_visits_on_one_day_count_once() -> None:
    result = annual([day(2024, 5, 2), day(2024, 5, 2)], day(2025, 3, 14))
    assert result.visits == (day(2024, 5, 2),)


def test_visits_are_sorted_however_they_arrive() -> None:
    result = annual([day(2024, 5, 2), day(2023, 5, 2)], day(2025, 3, 14))
    assert result.visits == (day(2023, 5, 2), day(2024, 5, 2))


def test_a_visit_in_the_future_is_refused() -> None:
    with pytest.raises(ValidationError):
        annual([day(2026, 5, 2)], day(2025, 3, 14))


def test_a_short_year_says_how_many_it_was_missing() -> None:
    visits = [day(2024, 1, 5), day(2024, 3, 5), day(2024, 5, 5)]
    result = evaluate_rule(
        RECTIFIER_BIMONTHLY, visits, asset_code="RU-3", as_of=day(2025, 1, 5)
    )
    short = result.short_years[0]
    assert short.year == 2024
    assert short.visits == 3
    assert short.short_by == 3
    assert "3 of 6 required visits" in result.reasons()[0]


def test_both_halves_can_fail_at_once() -> None:
    visits = [day(2024, 1, 5), day(2024, 12, 5)]
    result = evaluate_rule(
        RECTIFIER_BIMONTHLY, visits, asset_code="RU-3", as_of=day(2025, 1, 5)
    )
    assert result.short_years
    assert result.breaches
    assert len(result.reasons()) >= 2
