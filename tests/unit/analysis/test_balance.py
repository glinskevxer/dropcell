from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.balance import balance
from dropcell.errors import ValidationError
from dropcell.model.rectifier import Rectifier, RectifierCheck
from dropcell.stationing import Station


def unit(tag: str, metres: float, rated: float = 20.0) -> Rectifier:
    return Rectifier(
        tag=tag,
        line_code="AL-2",
        station=Station(metres),
        groundbed_code="GB-1",
        rated_voltage_v=24.0,
        rated_current_a=rated,
        coarse_taps=5,
        fine_taps=4,
        installed_on=dt.date(2004, 9, 1),
    )


def check(tag: str, amps: float) -> RectifierCheck:
    return RectifierCheck(
        rectifier_tag=tag,
        checked_on=dt.date(2025, 3, 14),
        output_voltage_v=18.5,
        output_current_a=amps,
        coarse_tap=3,
        fine_tap=2,
    )


def test_a_line_with_no_units_cannot_be_balanced() -> None:
    with pytest.raises(ValidationError):
        balance([], {})


def test_an_even_line_shares_the_work() -> None:
    units = [unit("RU-1", 0.0), unit("RU-2", 5000.0)]
    result = balance(units, {"RU-1": check("RU-1", 5.0), "RU-2": check("RU-2", 5.0)})
    assert result.total_a == pytest.approx(10.0)
    assert result.concentration == pytest.approx(0.5)
    assert not result.is_concentrated


def test_one_unit_carrying_the_line_is_concentrated() -> None:
    units = [unit("RU-1", 0.0), unit("RU-2", 5000.0)]
    result = balance(units, {"RU-1": check("RU-1", 9.0), "RU-2": check("RU-2", 1.0)})
    assert result.concentration == pytest.approx(0.9)
    assert result.is_concentrated


def test_a_single_unit_line_is_not_called_concentrated() -> None:
    result = balance([unit("RU-1", 0.0)], {"RU-1": check("RU-1", 9.0)})
    assert result.concentration == pytest.approx(1.0)
    assert not result.is_concentrated


def test_a_unit_nobody_has_read_counts_as_dead() -> None:
    units = [unit("RU-1", 0.0), unit("RU-2", 5000.0)]
    result = balance(units, {"RU-1": check("RU-1", 9.0), "RU-2": None})
    assert [item.tag for item in result.dead] == ["RU-2"]
    assert [item.tag for item in result.working] == ["RU-1"]


def test_a_unit_putting_out_nothing_counts_as_dead() -> None:
    result = balance([unit("RU-1", 0.0)], {"RU-1": check("RU-1", 0.0)})
    assert result.dead[0].tag == "RU-1"
    assert result.concentration == pytest.approx(0.0)


def test_a_unit_reports_its_load_and_its_spare() -> None:
    result = balance([unit("RU-1", 0.0)], {"RU-1": check("RU-1", 12.0)})
    share = result.units[0]
    assert share.load == pytest.approx(0.6)
    assert share.spare_a == pytest.approx(8.0)
    assert share.has_headroom


def test_a_unit_at_its_nameplate_has_no_headroom() -> None:
    result = balance([unit("RU-1", 0.0)], {"RU-1": check("RU-1", 19.0)})
    assert not result.units[0].has_headroom
    assert result.spare_a == pytest.approx(0.0)


def test_a_line_that_could_lose_its_biggest_unit_says_so() -> None:
    units = [unit("RU-1", 0.0), unit("RU-2", 5000.0), unit("RU-3", 9000.0)]
    latest = {
        "RU-1": check("RU-1", 6.0),
        "RU-2": check("RU-2", 4.0),
        "RU-3": check("RU-3", 4.0),
    }
    assert balance(units, latest).can_lose_the_biggest


def test_a_line_that_could_not_says_so() -> None:
    units = [unit("RU-1", 0.0, rated=20.0), unit("RU-2", 5000.0, rated=5.0)]
    latest = {"RU-1": check("RU-1", 18.0), "RU-2": check("RU-2", 4.0)}
    assert not balance(units, latest).can_lose_the_biggest


def test_a_line_with_nothing_working_cannot_lose_anything() -> None:
    result = balance([unit("RU-1", 0.0)], {"RU-1": None})
    assert not result.can_lose_the_biggest


def test_the_widest_gap_needs_two_units() -> None:
    assert balance([unit("RU-1", 0.0)], {"RU-1": check("RU-1", 5.0)}).widest_gap_m() is None


def test_the_widest_gap_is_between_neighbours() -> None:
    units = [unit("RU-1", 0.0), unit("RU-2", 1000.0), unit("RU-3", 9000.0)]
    latest = {tag: check(tag, 5.0) for tag in ("RU-1", "RU-2", "RU-3")}
    assert balance(units, latest).widest_gap_m() == pytest.approx(8000.0)


def test_the_summary_names_the_working_units_and_the_concentration() -> None:
    units = [unit("RU-1", 0.0), unit("RU-2", 5000.0)]
    result = balance(units, {"RU-1": check("RU-1", 9.0), "RU-2": None})
    text = result.summary()
    assert "AL-2: 1 of 2 units working" in text
    assert "largest carrying 100%" in text
