from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.groundbed import (
    amp_years,
    assess_bed,
    beds_due_within,
    rank_beds,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import AnodeMaterial, GroundbedKind
from dropcell.model.groundbed import Groundbed
from dropcell.model.rectifier import RectifierCheck


def bed(**overrides: object) -> Groundbed:
    kwargs: dict[str, object] = {
        "code": "GB-3",
        "kind": GroundbedKind.DEEP_WELL,
        "material": AnodeMaterial.HIGH_SILICON_IRON,
        "anode_count": 10,
        "anode_mass_kg": 20.0,
        "installed_on": dt.date(2004, 9, 1),
        "design_current_a": 15.0,
    }
    kwargs.update(overrides)
    return Groundbed(**kwargs)  # type: ignore[arg-type]


def check(day: dt.date, current: float) -> RectifierCheck:
    return RectifierCheck(
        rectifier_tag="RU-3",
        checked_on=day,
        output_voltage_v=18.5,
        output_current_a=current,
        coarse_tap=3,
        fine_tap=2,
    )


def test_no_checks_means_nothing_has_been_passed() -> None:
    assert amp_years([], until=dt.date(2025, 3, 14)) == pytest.approx(0.0)


def test_a_steady_ten_amps_for_a_year_is_ten_ampere_years() -> None:
    checks = [check(dt.date(2024, 1, 1), 10.0), check(dt.date(2025, 1, 1), 10.0)]
    assert amp_years(checks, until=dt.date(2025, 1, 1)) == pytest.approx(10.0, rel=0.01)


def test_the_current_between_two_checks_is_taken_as_the_average() -> None:
    checks = [check(dt.date(2024, 1, 1), 0.0), check(dt.date(2025, 1, 1), 20.0)]
    assert amp_years(checks, until=dt.date(2025, 1, 1)) == pytest.approx(10.0, rel=0.01)


def test_the_tail_from_the_last_check_to_today_is_counted() -> None:
    checks = [check(dt.date(2024, 1, 1), 10.0)]
    assert amp_years(checks, until=dt.date(2025, 1, 1)) == pytest.approx(10.0, rel=0.01)


def test_a_bed_read_once_and_left_accumulates_the_whole_gap() -> None:
    one = amp_years([check(dt.date(2023, 1, 1), 10.0)], until=dt.date(2025, 1, 1))
    assert one == pytest.approx(20.0, rel=0.01)


def test_checks_out_of_order_are_sorted_first() -> None:
    forward = [check(dt.date(2024, 1, 1), 10.0), check(dt.date(2025, 1, 1), 10.0)]
    backward = list(reversed(forward))
    until = dt.date(2025, 1, 1)
    assert amp_years(forward, until=until) == pytest.approx(amp_years(backward, until=until))


def test_a_check_after_the_date_being_worked_to_is_refused() -> None:
    with pytest.raises(ValidationError):
        amp_years([check(dt.date(2026, 1, 1), 10.0)], until=dt.date(2025, 1, 1))


def test_a_fresh_bed_has_spent_nothing() -> None:
    status = assess_bed(bed(), [], as_of=dt.date(2025, 3, 14))
    assert status.amp_years == pytest.approx(0.0)
    assert status.consumed_kg == pytest.approx(0.0)
    assert status.spent_fraction == pytest.approx(0.0)
    assert status.remaining_life_years is None
    assert status.projected_end is None
    assert not status.end_of_life


def test_a_worked_bed_reports_what_it_has_lost() -> None:
    checks = [check(dt.date(2015, 1, 1), 10.0), check(dt.date(2025, 1, 1), 10.0)]
    status = assess_bed(bed(), checks, as_of=dt.date(2025, 1, 1))
    assert status.amp_years == pytest.approx(100.0, rel=0.01)
    assert status.consumed_kg == pytest.approx(45.0, rel=0.01)
    assert status.remaining_kg == pytest.approx(125.0, rel=0.01)
    assert status.spent_percent == pytest.approx(100 * 45.0 / 170.0, rel=0.01)


def test_the_remaining_life_is_worked_at_the_present_output() -> None:
    checks = [check(dt.date(2015, 1, 1), 10.0), check(dt.date(2025, 1, 1), 10.0)]
    status = assess_bed(bed(), checks, as_of=dt.date(2025, 1, 1))
    assert status.present_current_a == pytest.approx(10.0)
    assert status.remaining_life_years is not None
    assert status.remaining_life_years == pytest.approx(125.0 / (10.0 * 0.45), rel=0.01)


def test_the_projected_end_falls_out_of_the_remaining_life() -> None:
    checks = [check(dt.date(2015, 1, 1), 10.0), check(dt.date(2025, 1, 1), 10.0)]
    status = assess_bed(bed(), checks, as_of=dt.date(2025, 1, 1))
    assert status.projected_end is not None
    assert status.projected_end.year > 2050


def test_a_dead_unit_leaves_the_remaining_life_unknown() -> None:
    checks = [check(dt.date(2024, 1, 1), 10.0), check(dt.date(2025, 1, 1), 0.0)]
    status = assess_bed(bed(), checks, as_of=dt.date(2025, 1, 1))
    assert status.present_current_a == pytest.approx(0.0)
    assert status.remaining_life_years is None
    assert status.projected_end is None


def test_a_bed_that_has_spent_itself_is_at_the_end_of_its_life() -> None:
    checks = [check(dt.date(1990, 1, 1), 15.0), check(dt.date(2025, 1, 1), 15.0)]
    status = assess_bed(bed(), checks, as_of=dt.date(2025, 1, 1))
    assert status.end_of_life
    assert status.spent_fraction == pytest.approx(1.0)
    assert status.remaining_kg == pytest.approx(0.0)


def test_ranking_puts_the_most_spent_bed_first() -> None:
    heavy = assess_bed(
        bed(code="GB-1"),
        [check(dt.date(2000, 1, 1), 15.0), check(dt.date(2025, 1, 1), 15.0)],
        as_of=dt.date(2025, 1, 1),
    )
    light = assess_bed(bed(code="GB-2"), [], as_of=dt.date(2025, 1, 1))
    assert [status.groundbed_code for status in rank_beds([light, heavy])] == ["GB-1", "GB-2"]


def test_ranking_breaks_a_tie_on_the_code() -> None:
    first = assess_bed(bed(code="GB-1"), [], as_of=dt.date(2025, 1, 1))
    second = assess_bed(bed(code="GB-2"), [], as_of=dt.date(2025, 1, 1))
    assert [status.groundbed_code for status in rank_beds([second, first])] == ["GB-1", "GB-2"]


def test_a_horizon_takes_the_beds_that_run_out_inside_it() -> None:
    nearly = assess_bed(
        bed(code="GB-1"),
        [check(dt.date(1998, 1, 1), 15.0), check(dt.date(2025, 1, 1), 15.0)],
        as_of=dt.date(2025, 1, 1),
    )
    fresh = assess_bed(
        bed(code="GB-2"),
        [check(dt.date(2024, 1, 1), 2.0), check(dt.date(2025, 1, 1), 2.0)],
        as_of=dt.date(2025, 1, 1),
    )
    due = beds_due_within([nearly, fresh], 5.0)
    assert [status.groundbed_code for status in due] == ["GB-1"]


def test_a_bed_already_finished_is_always_in_the_horizon() -> None:
    spent = assess_bed(
        bed(code="GB-1", installed_on=dt.date(1970, 1, 1)),
        [check(dt.date(1970, 1, 1), 15.0), check(dt.date(2025, 1, 1), 0.0)],
        as_of=dt.date(2025, 1, 1),
    )
    assert spent.end_of_life
    assert spent.remaining_life_years is None
    assert beds_due_within([spent], 0.0) == [spent]


def test_a_negative_horizon_is_refused() -> None:
    with pytest.raises(ValidationError):
        beds_due_within([], -1.0)
