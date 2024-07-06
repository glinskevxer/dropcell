from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.interference.stray import StrayCurrentLog, summarise


def log(samples: list[float], interval: float = 60.0) -> StrayCurrentLog:
    return StrayCurrentLog(
        test_point_code="TP-114",
        started_at=dt.datetime(2025, 3, 14, 6, 0),
        sample_interval_s=interval,
        samples_mv=tuple(samples),
    )


def test_the_code_is_normalised() -> None:
    assert log([-900.0, -900.0]).test_point_code == "TP-114"


def test_one_sample_is_not_a_log() -> None:
    with pytest.raises(ValidationError):
        log([-900.0])


def test_a_sample_interval_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        log([-900.0, -900.0], interval=0.0)


def test_the_duration_spans_the_gaps_not_the_samples() -> None:
    recorded = log([-900.0] * 61)
    assert recorded.count == 61
    assert recorded.duration_s == pytest.approx(3600.0)
    assert recorded.finished_at == dt.datetime(2025, 3, 14, 7, 0)


def test_the_mean_and_the_median_can_disagree() -> None:
    recorded = log([-900.0, -900.0, -900.0, -900.0, -200.0])
    assert recorded.median_mv == pytest.approx(-900.0)
    assert recorded.mean_mv > recorded.median_mv


def test_the_extremes_are_the_two_ends_of_the_swing() -> None:
    recorded = log([-1200.0, -900.0, -400.0])
    assert recorded.most_negative_mv == pytest.approx(-1200.0)
    assert recorded.most_positive_mv == pytest.approx(-400.0)
    assert recorded.swing_mv == pytest.approx(800.0)


def test_a_steady_post_is_not_dynamic() -> None:
    assert not log([-905.0, -900.0, -910.0]).is_dynamic()


def test_a_post_beside_a_tramway_is_dynamic() -> None:
    assert log([-1200.0, -900.0, -400.0]).is_dynamic()


def test_the_swing_limit_can_be_moved() -> None:
    recorded = log([-905.0, -900.0, -830.0])
    assert not recorded.is_dynamic()
    assert recorded.is_dynamic(swing_limit_mv=20.0)


def test_percentiles_interpolate_between_samples() -> None:
    recorded = log([-1000.0, -900.0, -800.0, -700.0, -600.0])
    assert recorded.percentile_mv(0.0) == pytest.approx(-1000.0)
    assert recorded.percentile_mv(0.5) == pytest.approx(-800.0)
    assert recorded.percentile_mv(1.0) == pytest.approx(-600.0)
    assert recorded.percentile_mv(0.25) == pytest.approx(-900.0)


@pytest.mark.parametrize("share", [-0.1, 1.1])
def test_a_percentile_outside_nought_to_one_is_refused(share: float) -> None:
    with pytest.raises(ValidationError):
        log([-900.0, -900.0]).percentile_mv(share)


def test_time_above_the_criterion_counts_the_samples_that_were_above_it() -> None:
    recorded = log([-900.0, -800.0, -820.0, -905.0])
    assert recorded.samples_above() == 2
    assert recorded.share_above() == pytest.approx(0.5)
    assert recorded.seconds_above() == pytest.approx(120.0)


def test_a_sample_exactly_on_the_criterion_is_not_above_it() -> None:
    assert log([-850.0, -850.0]).samples_above() == 0


def test_the_longest_excursion_is_the_worst_single_stretch() -> None:
    recorded = log([-800.0, -900.0, -800.0, -800.0, -800.0, -900.0, -800.0])
    assert recorded.samples_above() == 5
    assert recorded.longest_excursion_s() == pytest.approx(180.0)


def test_a_log_that_never_goes_above_has_no_excursion() -> None:
    assert log([-905.0, -910.0]).longest_excursion_s() == pytest.approx(0.0)


def test_a_log_entirely_above_is_one_long_excursion() -> None:
    recorded = log([-400.0, -400.0, -400.0])
    assert recorded.longest_excursion_s() == pytest.approx(180.0)


def test_the_threshold_can_be_moved_for_every_time_question() -> None:
    recorded = log([-900.0, -960.0, -905.0])
    assert recorded.samples_above(-950.0) == 2
    assert recorded.longest_excursion_s(-950.0) == pytest.approx(60.0)


def test_a_summary_carries_the_figures_a_report_needs() -> None:
    recorded = log([-1200.0, -800.0, -900.0, -700.0])
    summary = summarise(recorded)
    assert summary.test_point_code == "TP-114"
    assert summary.swing_mv == pytest.approx(500.0)
    assert summary.share_above == pytest.approx(0.5)
    assert summary.dynamic
    assert summary.duration_s == pytest.approx(180.0)


def test_a_summary_takes_the_same_thresholds_as_the_log() -> None:
    recorded = log([-900.0, -960.0, -905.0])
    summary = summarise(recorded, threshold_mv=-950.0, swing_limit_mv=10.0)
    assert summary.share_above == pytest.approx(2 / 3)
    assert summary.dynamic
