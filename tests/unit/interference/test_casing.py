from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.interference.casing import (
    CasingStatus,
    CasingTest,
    classify_casing,
)
from dropcell.stationing import Station


def casing_test(**overrides: object) -> CasingTest:
    kwargs: dict[str, object] = {
        "casing_code": "CS-12",
        "line_code": "AL-2",
        "station": Station(1245.5),
        "tested_on": dt.date(2025, 3, 14),
        "pipe_on_mv": -1120.0,
        "casing_on_mv": -560.0,
    }
    kwargs.update(overrides)
    return CasingTest(**kwargs)  # type: ignore[arg-type]


def test_a_casing_sitting_on_its_own_is_clear() -> None:
    result = classify_casing(casing_test())
    assert result.status is CasingStatus.CLEAR
    assert result.due_by is None


def test_a_casing_dragged_part_way_across_is_electrolytic() -> None:
    result = classify_casing(casing_test(casing_on_mv=-1060.0))
    assert result.status is CasingStatus.ELECTROLYTIC
    assert result.separation_mv == pytest.approx(60.0)
    assert result.due_by == dt.date(2026, 3, 14)


def test_two_readings_that_sit_together_are_a_metallic_short() -> None:
    result = classify_casing(casing_test(casing_on_mv=-1116.0))
    assert result.status is CasingStatus.METALLIC_SHORT
    assert result.due_by == dt.date(2025, 6, 12)


def test_the_off_readings_are_preferred_when_they_are_there() -> None:
    on_readings_look_clear = casing_test(
        casing_on_mv=-1115.0, pipe_off_mv=-905.0, casing_off_mv=-900.0
    )
    result = classify_casing(on_readings_look_clear)
    assert result.status is CasingStatus.METALLIC_SHORT
    assert result.separation_mv == pytest.approx(5.0)


def test_readings_that_sit_together_and_shift_together_are_a_short() -> None:
    result = classify_casing(
        casing_test(
            pipe_on_mv=-1120.0,
            casing_on_mv=-1118.0,
            pipe_off_mv=-905.0,
            casing_off_mv=-903.0,
        )
    )
    assert result.status is CasingStatus.METALLIC_SHORT


def test_readings_that_sit_together_but_shift_apart_are_indeterminate() -> None:
    result = classify_casing(
        casing_test(
            pipe_on_mv=-1120.0,
            casing_on_mv=-1000.0,
            pipe_off_mv=-905.0,
            casing_off_mv=-900.0,
        )
    )
    assert result.status is CasingStatus.INDETERMINATE
    assert "shift together" in result.reason


def test_moving_together_needs_both_off_readings() -> None:
    assert casing_test().moves_together is None
    assert casing_test(pipe_off_mv=-905.0).moves_together is None
    both = casing_test(pipe_off_mv=-905.0, casing_off_mv=-900.0, casing_on_mv=-1115.0)
    assert both.moves_together is True


def test_the_bands_can_be_moved() -> None:
    reading = casing_test(casing_on_mv=-1060.0)
    assert classify_casing(reading).status is CasingStatus.ELECTROLYTIC
    assert (
        classify_casing(reading, short_mv=80.0, electrolytic_mv=200.0).status
        is CasingStatus.METALLIC_SHORT
    )


def test_bands_that_overlap_are_refused() -> None:
    with pytest.raises(ValidationError):
        classify_casing(casing_test(), short_mv=100.0, electrolytic_mv=50.0)
    with pytest.raises(ValidationError):
        classify_casing(casing_test(), short_mv=0.0)


def test_only_the_two_short_states_put_a_crossing_on_a_work_list() -> None:
    assert CasingStatus.METALLIC_SHORT.needs_work
    assert CasingStatus.ELECTROLYTIC.needs_work
    assert not CasingStatus.CLEAR.needs_work
    assert not CasingStatus.INDETERMINATE.needs_work


def test_an_indeterminate_result_is_looked_at_soonest_of_all() -> None:
    assert CasingStatus.INDETERMINATE.response_days == 60


def test_codes_are_normalised_on_the_way_in() -> None:
    reading = casing_test(casing_code="cs 12", line_code="al-2")
    assert (reading.casing_code, reading.line_code) == ("CS-12", "AL-2")


def test_an_impossible_potential_is_refused() -> None:
    with pytest.raises(ValidationError):
        casing_test(casing_on_mv=-9000.0)
    with pytest.raises(ValidationError):
        casing_test(pipe_off_mv=4000.0)
