from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.model.enums import Commodity
from dropcell.model.line import Line
from dropcell.stationing import Convention, Station


def make_line(**overrides: object) -> Line:
    kwargs: dict[str, object] = {
        "code": "AL-2",
        "name": "Ashfield lateral",
        "operator": "Northmoor Gas",
        "commodity": Commodity.NATURAL_GAS,
        "length_m": 18_500.0,
        "nominal_diameter_mm": 323.9,
        "installed_year": 1974,
    }
    kwargs.update(overrides)
    return Line(**kwargs)  # type: ignore[arg-type]


def test_the_code_is_normalised_on_the_way_in() -> None:
    assert make_line(code=" al 2 ").code == "AL-2"


def test_blank_names_and_operators_are_refused() -> None:
    with pytest.raises(ValidationError):
        make_line(name="  ")
    with pytest.raises(ValidationError):
        make_line(operator="")


def test_names_are_trimmed_rather_than_stored_as_typed() -> None:
    assert make_line(name="  Ashfield lateral  ").name == "Ashfield lateral"


@pytest.mark.parametrize("length", [0.0, -1.0])
def test_a_line_with_no_length_is_refused(length: float) -> None:
    with pytest.raises(ValidationError):
        make_line(length_m=length)


def test_a_line_with_no_diameter_is_refused() -> None:
    with pytest.raises(ValidationError):
        make_line(nominal_diameter_mm=0.0)


@pytest.mark.parametrize("year", [1700, dt.date.today().year + 1])
def test_an_impossible_install_year_is_refused(year: int) -> None:
    with pytest.raises(ValidationError):
        make_line(installed_year=year)


def test_the_extent_runs_from_the_origin_to_the_length() -> None:
    line = make_line()
    assert line.extent.start == Station(0.0)
    assert line.extent.end == Station(18_500.0)
    assert line.extent.length_m == pytest.approx(18_500.0)


def test_diameter_converts_to_the_inches_everyone_says_out_loud() -> None:
    assert make_line().nominal_diameter_in == pytest.approx(12.75, abs=0.01)


def test_age_counts_whole_years_since_the_line_went_in() -> None:
    line = make_line(installed_year=dt.date.today().year - 40)
    assert line.age_years == 40


def test_stations_are_read_in_the_line_convention() -> None:
    imperial = make_line()
    assert imperial.station("10+00.00").metres == pytest.approx(1000 * 0.3048)
    metric = make_line(convention=Convention.METRIC)
    assert metric.station("1+000.0").metres == pytest.approx(1000.0)


def test_ranges_are_read_in_the_line_convention_too() -> None:
    metric = make_line(convention=Convention.METRIC)
    span = metric.span("1+000.0 to 1+400.0")
    assert span.length_m == pytest.approx(400.0)


def test_formatting_puts_a_station_back_into_the_line_convention() -> None:
    metric = make_line(convention=Convention.METRIC)
    assert metric.format_station(Station(1234.5)) == "1+234.5"


def test_a_station_past_the_end_is_not_on_the_line() -> None:
    line = make_line()
    assert line.covers(Station(0.0))
    assert line.covers(Station(18_500.0))
    assert not line.covers(Station(18_500.1))
    assert not line.covers(Station(-0.1))


def test_requiring_a_station_on_the_line_returns_it_or_refuses() -> None:
    line = make_line()
    assert line.require_on_line(Station(500.0)) == Station(500.0)
    with pytest.raises(ValidationError) as caught:
        line.require_on_line(Station(99_000.0))
    assert caught.value.detail["code"] == "AL-2"


def test_notes_do_not_take_part_in_equality() -> None:
    assert make_line(notes="rebuilt 1998") == make_line(notes="")


def test_gas_is_not_a_hazardous_liquid_but_crude_is() -> None:
    assert not Commodity.NATURAL_GAS.is_hazardous_liquid
    assert Commodity.CRUDE_OIL.is_hazardous_liquid
    assert Commodity.NATURAL_GAS_LIQUIDS.is_hazardous_liquid
