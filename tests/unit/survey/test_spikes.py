from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.stationing import Station
from dropcell.survey.cis import CisPoint, CisSurvey
from dropcell.survey.spikes import Spike, find_spikes, without_spikes


def survey(pairs: list[tuple[float, float | None]]) -> CisSurvey:
    return CisSurvey(
        line_code="AL-2",
        taken_on=dt.date(2025, 3, 14),
        nominal_interval_m=1.0,
        points=tuple(
            CisPoint(station=Station(float(index)), on_mv=on, off_mv=off)
            for index, (on, off) in enumerate(pairs)
        ),
    )


def steady(count: int) -> list[tuple[float, float | None]]:
    return [(-1120.0, -905.0)] * count


def test_a_steady_trace_has_no_spikes() -> None:
    assert find_spikes(survey(steady(9))) == []


def test_a_step_where_both_traces_jump_together_is_a_contact_problem() -> None:
    pairs = steady(9)
    pairs[4] = (-620.0, -400.0)
    spikes = find_spikes(survey(pairs))
    assert [spike.index for spike in spikes] == [4]
    assert spikes[0].departure_mv == pytest.approx(505.0)


def test_a_step_where_only_the_off_moves_is_a_real_defect() -> None:
    pairs = steady(9)
    pairs[4] = (-1120.0, -400.0)
    assert find_spikes(survey(pairs)) == []


def test_a_step_that_goes_more_negative_is_never_a_contact_problem() -> None:
    pairs = steady(9)
    pairs[4] = (-1620.0, -1405.0)
    assert find_spikes(survey(pairs)) == []


def test_a_small_wobble_is_left_alone() -> None:
    pairs = steady(9)
    pairs[4] = (-1020.0, -805.0)
    assert find_spikes(survey(pairs)) == []


def test_the_departure_threshold_can_be_tightened() -> None:
    pairs = steady(9)
    pairs[4] = (-1020.0, -805.0)
    assert len(find_spikes(survey(pairs), departure_mv=50.0)) == 1


def test_the_ir_tolerance_decides_how_much_drift_still_counts() -> None:
    pairs = steady(9)
    pairs[4] = (-600.0, -400.0)
    assert find_spikes(survey(pairs), ir_tolerance_mv=5.0) == []
    assert len(find_spikes(survey(pairs), ir_tolerance_mv=40.0)) == 1


def test_a_step_with_no_off_reading_cannot_be_a_spike() -> None:
    pairs = steady(9)
    pairs[4] = (-620.0, None)
    assert find_spikes(survey(pairs)) == []


def test_two_spikes_are_both_reported() -> None:
    pairs = steady(11)
    pairs[3] = (-620.0, -400.0)
    pairs[8] = (-600.0, -390.0)
    assert [spike.index for spike in find_spikes(survey(pairs))] == [3, 8]


def test_a_spike_carries_where_it_was_and_what_it_departed_from() -> None:
    pairs = steady(9)
    pairs[4] = (-620.0, -400.0)
    spike = find_spikes(survey(pairs))[0]
    assert spike.station_m == pytest.approx(4.0)
    assert spike.local_median_off_mv == pytest.approx(-905.0)
    assert spike.ir_change_mv == pytest.approx(-5.0)


@pytest.mark.parametrize("window", [2, 4, 1, 0])
def test_an_even_or_tiny_window_is_refused(window: int) -> None:
    with pytest.raises(ValidationError):
        find_spikes(survey(steady(9)), window=window)


def test_a_non_positive_departure_is_refused() -> None:
    with pytest.raises(ValidationError):
        find_spikes(survey(steady(9)), departure_mv=0.0)


def test_filtering_returns_a_copy_without_the_suspect_steps() -> None:
    pairs = steady(9)
    pairs[4] = (-620.0, -400.0)
    original = survey(pairs)
    spikes = find_spikes(original)
    cleaned = without_spikes(original, spikes)
    assert len(cleaned.points) == 8
    assert len(original.points) == 9
    assert all(point.off_mv == pytest.approx(-905.0) for point in cleaned.points)


def test_filtering_keeps_everything_else_about_the_survey() -> None:
    original = survey(steady(9))
    cleaned = without_spikes(original, [])
    assert cleaned.line_code == original.line_code
    assert cleaned.taken_on == original.taken_on
    assert cleaned.nominal_interval_m == pytest.approx(original.nominal_interval_m)


def test_filtering_everything_away_is_refused() -> None:
    walked = survey(steady(3))
    everything = [
        Spike(
            index=index,
            point=point,
            local_median_off_mv=-905.0,
            departure_mv=0.0,
            ir_change_mv=0.0,
        )
        for index, point in enumerate(walked.points)
    ]
    with pytest.raises(ValidationError) as caught:
        without_spikes(walked, everything)
    assert caught.value.detail["removed"] == 3
