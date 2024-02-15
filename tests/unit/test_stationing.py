from __future__ import annotations

import pytest

from dropcell.errors import StationError
from dropcell.stationing import Convention, Station


def test_a_foot_station_counts_hundreds_of_feet() -> None:
    assert Station.parse("12+45.50").metres == pytest.approx(1245.50 * 0.3048)


def test_a_metric_station_counts_kilometres() -> None:
    station = Station.parse("1+000.0", Convention.METRIC)
    assert station.metres == pytest.approx(1000.0)


def test_zero_station_is_the_line_origin() -> None:
    assert Station.parse("0+00.00").metres == pytest.approx(0.0)


def test_a_plain_distance_with_a_unit_is_also_a_station() -> None:
    assert Station.parse("1245.5 ft").metres == pytest.approx(1245.5 * 0.3048)
    assert Station.parse("2500 m").metres == pytest.approx(2500.0)


def test_a_bare_number_is_read_as_metres() -> None:
    assert Station.parse("400").metres == pytest.approx(400.0)


def test_a_negative_station_sits_behind_the_origin() -> None:
    assert Station.parse("-1+50.00").metres == pytest.approx(-150.0 * 0.3048)


@pytest.mark.parametrize(
    ("text", "convention"),
    [
        ("12+100.00", Convention.FOOT),
        ("1+1000.0", Convention.METRIC),
        ("12+99.99+3", Convention.FOOT),
        ("station twelve", Convention.FOOT),
        ("", Convention.FOOT),
    ],
)
def test_a_malformed_station_raises(text: str, convention: Convention) -> None:
    with pytest.raises(StationError):
        Station.parse(text, convention)


def test_the_overflow_error_names_the_limit_it_broke() -> None:
    with pytest.raises(StationError) as caught:
        Station.parse("12+100.00")
    assert caught.value.detail["limit"] == 100


def test_formatting_a_foot_station_pads_the_minor_part() -> None:
    assert Station.parse("12+45.50").format() == "12+45.50"
    assert Station.parse("0+05.00").format() == "0+05.00"


def test_formatting_a_metric_station_pads_to_three_digits() -> None:
    station = Station.parse("3+007.5", Convention.METRIC)
    assert station.format(Convention.METRIC) == "3+007.5"


def test_a_minor_part_that_rounds_up_carries_into_the_major() -> None:
    station = Station(99.999 * 0.3048)
    assert station.format() == "1+00.00"


def test_a_negative_station_prints_its_sign() -> None:
    assert Station(-150.0 * 0.3048).format() == "-1+50.00"


def test_a_station_survives_a_round_trip_through_text() -> None:
    for text in ["0+00.00", "7+22.75", "148+99.99"]:
        assert Station.parse(text).format() == text


def test_stations_compare_and_sort_on_distance() -> None:
    stations = [Station.parse("12+00.00"), Station.parse("3+50.00"), Station.parse("0+00.00")]
    assert [s.format() for s in sorted(stations)] == ["0+00.00", "3+50.00", "12+00.00"]
    assert Station(10.0) < Station(11.0)
    assert Station(10.0) == Station(10.0)


def test_the_distance_between_two_stations_is_signed() -> None:
    near = Station.parse("1+00.00")
    far = Station.parse("4+00.00")
    assert near.to(far) == pytest.approx(300 * 0.3048)
    assert far.to(near) == pytest.approx(-300 * 0.3048)


def test_shifting_a_station_moves_it_along_the_line() -> None:
    assert Station(100.0).shifted(25.0) == Station(125.0)
    assert Station(100.0).shifted(-25.0) == Station(75.0)


def test_a_station_is_hashable_so_it_can_key_a_dict() -> None:
    counts = {Station(10.0): 3}
    counts[Station(10.0)] += 1
    assert counts == {Station(10.0): 4}


def test_str_uses_the_foot_convention_by_default() -> None:
    assert str(Station.parse("12+45.50")) == "12+45.50"


def test_the_conventions_carry_their_own_arithmetic() -> None:
    assert Convention.FOOT.major_metres == pytest.approx(30.48)
    assert Convention.METRIC.major_metres == pytest.approx(1000.0)
    assert Convention.FOOT.minors_per_major == 100
    assert Convention.METRIC.minor_digits == 3
