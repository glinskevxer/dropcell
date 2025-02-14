from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.rectifier import (
    UnitFault,
    assess_unit,
    running_share,
    urgent_first,
)
from dropcell.errors import ValidationError
from dropcell.model.rectifier import Rectifier, RectifierCheck
from dropcell.stationing import Station


def unit(tag: str = "RU-3", rated: float = 20.0) -> Rectifier:
    return Rectifier(
        tag=tag,
        line_code="AL-2",
        station=Station(4210.0),
        groundbed_code="GB-3",
        rated_voltage_v=24.0,
        rated_current_a=rated,
        coarse_taps=5,
        fine_taps=4,
        installed_on=dt.date(2004, 9, 1),
    )


def check(
    day: dt.date,
    volts: float = 18.5,
    amps: float = 12.4,
    coarse: int = 3,
    fine: int = 2,
    hours: float | None = None,
) -> RectifierCheck:
    return RectifierCheck(
        rectifier_tag="RU-3",
        checked_on=day,
        output_voltage_v=volts,
        output_current_a=amps,
        coarse_tap=coarse,
        fine_tap=fine,
        hour_meter=hours,
    )


def months(count: int) -> list[dt.date]:
    return [dt.date(2024, 1 + index * 2, 6) for index in range(count)]


def test_a_unit_nobody_has_checked_says_so() -> None:
    result = assess_unit(unit(), [])
    assert result.checks == 0
    assert result.latest is None
    assert result.notes == ("never checked",)
    assert result.healthy


def test_a_steady_unit_has_nothing_found() -> None:
    checks = [check(day) for day in months(6)]
    result = assess_unit(unit(), checks)
    assert result.healthy
    assert "nothing found over 6 checks" in result.render()


def test_a_dead_unit_is_urgent() -> None:
    checks = [check(day) for day in months(5)] + [check(months(6)[-1], amps=0.0)]
    result = assess_unit(unit(), checks)
    assert UnitFault.DEAD in result.faults
    assert result.urgent


def test_a_unit_at_its_nameplate_is_reported() -> None:
    checks = [check(day, amps=19.0) for day in months(3)]
    result = assess_unit(unit(), checks)
    assert UnitFault.AT_CAPACITY in result.faults
    assert not result.urgent


def test_a_falling_output_is_reported() -> None:
    days = months(4)
    checks = [
        check(days[0], amps=12.0),
        check(days[1], amps=11.0),
        check(days[2], amps=9.0),
        check(days[3], amps=7.0),
    ]
    result = assess_unit(unit(), checks)
    assert UnitFault.OUTPUT_FALLING in result.faults
    assert any("output down" in note for note in result.notes)


def test_a_small_drift_in_output_is_not_reported() -> None:
    days = months(3)
    checks = [check(days[0], amps=12.0), check(days[1], amps=11.8), check(days[2], amps=11.5)]
    assert assess_unit(unit(), checks).healthy


def test_a_climbing_circuit_resistance_is_reported() -> None:
    days = months(3)
    checks = [
        check(days[0], volts=12.0, amps=12.0),
        check(days[1], volts=16.0, amps=11.0),
        check(days[2], volts=22.0, amps=10.0),
    ]
    result = assess_unit(unit(), checks)
    assert UnitFault.RESISTANCE_CLIMBING in result.faults


def test_taps_wound_up_at_every_visit_are_reported() -> None:
    days = months(4)
    checks = [
        check(days[0], coarse=1, fine=1),
        check(days[1], coarse=1, fine=2),
        check(days[2], coarse=2, fine=1),
        check(days[3], coarse=2, fine=3),
    ]
    result = assess_unit(unit(), checks)
    assert UnitFault.TAPS_CLIMBING in result.faults


def test_taps_that_went_back_down_are_not_reported() -> None:
    days = months(4)
    checks = [
        check(days[0], coarse=1, fine=1),
        check(days[1], coarse=2, fine=1),
        check(days[2], coarse=1, fine=1),
        check(days[3], coarse=2, fine=1),
    ]
    assert UnitFault.TAPS_CLIMBING not in assess_unit(unit(), checks).faults


def test_taps_that_never_moved_are_not_reported() -> None:
    checks = [check(day) for day in months(4)]
    assert UnitFault.TAPS_CLIMBING not in assess_unit(unit(), checks).faults


def test_the_running_share_compares_the_meter_with_the_calendar() -> None:
    first = check(dt.date(2024, 1, 1), hours=1000.0)
    second = check(dt.date(2024, 1, 11), hours=1240.0)
    assert running_share(first, second) == pytest.approx(1.0)


def test_a_unit_that_was_off_half_the_time_says_so() -> None:
    first = check(dt.date(2024, 1, 1), hours=1000.0)
    second = check(dt.date(2024, 1, 11), hours=1120.0)
    assert running_share(first, second) == pytest.approx(0.5)


def test_a_meter_that_went_backwards_is_refused() -> None:
    first = check(dt.date(2024, 1, 1), hours=1000.0)
    second = check(dt.date(2024, 1, 11), hours=900.0)
    with pytest.raises(ValidationError):
        running_share(first, second)


def test_a_missing_meter_reading_gives_no_share() -> None:
    first = check(dt.date(2024, 1, 1), hours=1000.0)
    second = check(dt.date(2024, 1, 11))
    assert running_share(first, second) is None


def test_a_unit_that_keeps_tripping_is_urgent() -> None:
    checks = [
        check(dt.date(2024, 1, 1), hours=1000.0),
        check(dt.date(2024, 3, 1), hours=1600.0),
        check(dt.date(2024, 5, 1), hours=3000.0),
    ]
    result = assess_unit(unit(), checks)
    assert UnitFault.NOT_RUNNING in result.faults
    assert result.urgent


def test_a_unit_that_ran_the_whole_time_is_not_reported() -> None:
    checks = [
        check(dt.date(2024, 1, 1), hours=1000.0),
        check(dt.date(2024, 3, 1), hours=1000.0 + 60 * 24),
        check(dt.date(2024, 5, 1), hours=1000.0 + 121 * 24),
    ]
    assert UnitFault.NOT_RUNNING not in assess_unit(unit(), checks).faults


def test_only_the_recent_window_is_read() -> None:
    days = [dt.date(2020 + index, 1, 6) for index in range(6)]
    checks = [check(days[0], amps=20.0)] + [check(day, amps=12.0) for day in days[1:]]
    assert assess_unit(unit(), checks, window=3).healthy
    assert UnitFault.OUTPUT_FALLING in assess_unit(unit(), checks, window=6).faults


def test_a_window_of_one_is_refused() -> None:
    with pytest.raises(ValidationError):
        assess_unit(unit(), [check(dt.date(2024, 1, 1))], window=1)


def test_urgent_units_sort_before_the_rest() -> None:
    dead = assess_unit(unit("RU-1"), [check(day, amps=0.0) for day in months(3)])
    loaded = assess_unit(unit("RU-2"), [check(day, amps=19.0) for day in months(3)])
    fine = assess_unit(unit("RU-3"), [check(day) for day in months(3)])
    order = [item.tag for item in urgent_first([fine, loaded, dead])]
    assert order == ["RU-1", "RU-2", "RU-3"]
