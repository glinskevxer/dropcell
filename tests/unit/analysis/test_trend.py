from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.trend import crossing_within, fit_trend, worst_drift_first
from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.reading import Reading


def reading(year: int, off_mv: float | None, on_mv: float = -1120.0) -> Reading:
    return Reading(
        test_point_code="TP-114",
        lead=LeadKind.PIPE,
        taken_on=dt.date(year, 5, 2),
        on_mv=on_mv,
        off_mv=off_mv,
    )


def test_too_few_readings_gives_no_trend() -> None:
    assert fit_trend("TP-114", []) is None
    assert fit_trend("TP-114", [reading(2023, -1000.0), reading(2024, -950.0)]) is None


def test_readings_with_no_off_potential_do_not_count() -> None:
    history = [reading(2022, None), reading(2023, None), reading(2024, -950.0)]
    assert fit_trend("TP-114", history) is None


def test_a_flat_history_has_no_slope() -> None:
    history = [reading(year, -905.0) for year in (2022, 2023, 2024)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    assert trend.slope_mv_per_year == pytest.approx(0.0, abs=1e-6)
    assert not trend.drifting_positive


def test_a_post_losing_protection_has_a_positive_slope() -> None:
    history = [reading(2022, -1000.0), reading(2023, -950.0), reading(2024, -900.0)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    assert trend.slope_mv_per_year == pytest.approx(50.0, rel=0.02)
    assert trend.drifting_positive


def test_a_post_gaining_protection_has_a_negative_slope() -> None:
    history = [reading(2022, -900.0), reading(2023, -950.0), reading(2024, -1000.0)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    assert trend.slope_mv_per_year < 0


def test_the_trend_carries_its_span_and_its_latest_reading() -> None:
    history = [reading(2022, -1000.0), reading(2023, -950.0), reading(2024, -900.0)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    assert trend.readings == 3
    assert trend.span_years == pytest.approx(2.0, rel=0.01)
    assert trend.latest_mv == pytest.approx(-900.0)


def test_readings_out_of_order_are_sorted_first() -> None:
    forward = [reading(2022, -1000.0), reading(2023, -950.0), reading(2024, -900.0)]
    trend = fit_trend("TP-114", list(reversed(forward)))
    assert trend is not None
    assert trend.first_on.year == 2022
    assert trend.last_on.year == 2024


def test_a_noisy_history_has_a_bigger_residual() -> None:
    clean = fit_trend(
        "TP-114", [reading(y, -1000.0 + 50 * (y - 2022)) for y in (2022, 2023, 2024)]
    )
    noisy = fit_trend(
        "TP-114", [reading(2022, -1000.0), reading(2023, -800.0), reading(2024, -900.0)]
    )
    assert clean is not None
    assert noisy is not None
    assert noisy.residual_mv > clean.residual_mv


def test_the_line_can_be_read_at_any_date() -> None:
    history = [reading(2022, -1000.0), reading(2023, -950.0), reading(2024, -900.0)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    assert trend.value_at(dt.date(2022, 5, 2)) == pytest.approx(-1000.0, rel=0.01)
    assert trend.value_at(dt.date(2025, 5, 2)) == pytest.approx(-850.0, rel=0.02)


def test_a_flat_post_never_crosses_the_threshold() -> None:
    trend = fit_trend("TP-114", [reading(year, -905.0) for year in (2022, 2023, 2024)])
    assert trend is not None
    assert trend.crosses() is None


def test_a_drifting_post_crosses_inside_the_horizon() -> None:
    history = [reading(2022, -1000.0), reading(2023, -950.0), reading(2024, -900.0)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    crossing = trend.crosses()
    assert crossing is not None
    assert crossing.year == 2025


def test_a_post_already_past_the_threshold_crosses_at_its_last_reading() -> None:
    history = [reading(2022, -900.0), reading(2023, -850.0), reading(2024, -800.0)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    assert trend.crosses() == dt.date(2024, 5, 2)


def test_a_slope_too_slow_to_matter_gives_no_crossing() -> None:
    history = [reading(2022, -1000.0), reading(2023, -999.0), reading(2024, -998.0)]
    trend = fit_trend("TP-114", history)
    assert trend is not None
    assert trend.crosses(horizon_years=5.0) is None


def test_a_horizon_that_runs_backwards_is_refused() -> None:
    trend = fit_trend("TP-114", [reading(y, -905.0) for y in (2022, 2023, 2024)])
    assert trend is not None
    with pytest.raises(ValidationError):
        trend.crosses(horizon_years=0.0)


def test_the_on_trace_can_be_fitted_instead() -> None:
    history = [
        reading(2022, None, on_mv=-1200.0),
        reading(2023, None, on_mv=-1150.0),
        reading(2024, None, on_mv=-1100.0),
    ]
    trend = fit_trend("TP-114", history, use_off=False)
    assert trend is not None
    assert trend.slope_mv_per_year == pytest.approx(50.0, rel=0.02)


def test_ordering_puts_the_fastest_drift_first() -> None:
    fast = fit_trend(
        "TP-1", [reading(2022, -1000.0), reading(2023, -900.0), reading(2024, -800.0)]
    )
    slow = fit_trend(
        "TP-2", [reading(2022, -1000.0), reading(2023, -990.0), reading(2024, -980.0)]
    )
    assert fast is not None
    assert slow is not None
    assert [item.test_point_code for item in worst_drift_first([slow, fast])] == [
        "TP-1",
        "TP-2",
    ]


def test_a_horizon_picks_out_the_posts_that_will_fail_in_it() -> None:
    soon = fit_trend(
        "TP-1", [reading(2022, -1000.0), reading(2023, -950.0), reading(2024, -900.0)]
    )
    never = fit_trend("TP-2", [reading(y, -1200.0) for y in (2022, 2023, 2024)])
    assert soon is not None
    assert never is not None
    picked = crossing_within([soon, never], 5.0)
    assert [item.test_point_code for item in picked] == ["TP-1"]
