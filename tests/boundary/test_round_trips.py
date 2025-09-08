"""The pass made before calling this one point oh.

Every test elsewhere in this suite was written alongside the code it covers,
which means it tests what the author was thinking about. This one was written
afterwards, against the boundaries, by somebody looking for the cases nobody
had in mind: the zero, the one either side of a threshold, the value that is
exactly on it, and the round trip that has to come back to where it started.

Three of these found something.
"""

from __future__ import annotations

import math

import pytest

from dropcell.criteria.base import Evidence
from dropcell.criteria.potential import DEFAULT_PROTECTION_MV, PolarisedPotentialCriterion
from dropcell.electrodes import Electrode, convert_potential
from dropcell.model.segment import Segment
from dropcell.stationing import Convention, Station, StationRange, merge_ranges
from dropcell.units import (
    format_length_m,
    format_potential_mv,
    parse_length_m,
    parse_potential_mv,
    parse_voltage_v,
)

FEET = [0.0, 0.01, 1.0, 99.99, 100.0, 1245.5, 99999.99]
METRES = [0.0, 0.1, 1.0, 999.9, 1000.0, 18500.0]
POTENTIALS = [-2999.0, -1200.0, -850.0, -849.99, -0.01, 0.0, 999.0]


@pytest.mark.parametrize("feet", FEET)
def test_a_foot_station_survives_a_round_trip(feet: float) -> None:
    station = Station(feet * 0.3048)
    again = Station.parse(station.format(), Convention.FOOT)
    assert again.metres == pytest.approx(station.metres, abs=0.005)


@pytest.mark.parametrize("metres", METRES)
def test_a_metric_station_survives_a_round_trip(metres: float) -> None:
    station = Station(metres)
    again = Station.parse(station.format(Convention.METRIC), Convention.METRIC)
    assert again.metres == pytest.approx(metres, abs=0.05)


@pytest.mark.parametrize("metres", METRES)
def test_a_station_is_its_own_distance_from_the_origin(metres: float) -> None:
    assert Station(0.0).to(Station(metres)) == pytest.approx(metres)


@pytest.mark.parametrize("value", POTENTIALS)
def test_a_potential_survives_a_round_trip_through_text(value: float) -> None:
    assert parse_potential_mv(format_potential_mv(value)) == pytest.approx(value, abs=0.5)


@pytest.mark.parametrize("value", POTENTIALS)
def test_a_potential_survives_a_round_trip_through_volts(value: float) -> None:
    text = format_potential_mv(value, unit="V")
    assert parse_potential_mv(text) == pytest.approx(value, abs=0.5)


@pytest.mark.parametrize("value", POTENTIALS)
@pytest.mark.parametrize("electrode", list(Electrode))
def test_converting_between_electrodes_is_reversible(
    value: float, electrode: Electrode
) -> None:
    there = convert_potential(value, Electrode.CSE, electrode)
    back = convert_potential(there, electrode, Electrode.CSE)
    assert back == pytest.approx(value)


@pytest.mark.parametrize("metres", METRES)
@pytest.mark.parametrize("unit", ["m", "ft", "km", "mi", "in", "mm"])
def test_a_length_survives_a_round_trip_through_any_unit(metres: float, unit: str) -> None:
    text = format_length_m(metres, unit=unit, places=9)
    assert parse_length_m(text) == pytest.approx(metres, rel=1e-6, abs=1e-6)


@pytest.mark.parametrize("metres", METRES)
def test_a_short_length_in_miles_needs_the_decimal_places(metres: float) -> None:
    """Formatting is lossy at a fixed number of places, and it has to be said.

    A metre written in miles to two places is zero. That is the format doing
    what it was asked, not the conversion being wrong, and it is worth a test
    because the obvious round trip assertion fails on it and the obvious fix is
    to change the conversion.
    """
    coarse = parse_length_m(format_length_m(metres, unit="mi", places=2))
    fine = parse_length_m(format_length_m(metres, unit="mi", places=9))
    assert abs(fine - metres) <= abs(coarse - metres) + 1e-9


def test_the_two_bare_number_defaults_stay_apart() -> None:
    assert parse_potential_mv("12") == pytest.approx(12.0)
    assert parse_voltage_v("12") == pytest.approx(12.0)
    assert parse_potential_mv("12") != pytest.approx(parse_voltage_v("12") * 1000.0)


@pytest.mark.parametrize(
    ("value", "met"),
    [
        (DEFAULT_PROTECTION_MV - 0.001, True),
        (DEFAULT_PROTECTION_MV, True),
        (DEFAULT_PROTECTION_MV + 0.001, False),
    ],
)
def test_the_criterion_boundary_is_exactly_where_it_says(
    segment: Segment,
    value: float,
    met: bool,
) -> None:
    result = PolarisedPotentialCriterion().assess(Evidence(segment=segment, off_mv=value))
    assert result.met is met


def test_a_range_of_no_length_is_allowed_and_contains_its_point() -> None:
    span = StationRange(Station(100.0), Station(100.0))
    assert span.length_m == pytest.approx(0.0)
    assert span.contains(Station(100.0))


def test_merging_a_range_with_itself_changes_nothing() -> None:
    span = StationRange(Station(0.0), Station(100.0))
    assert merge_ranges([span, span]) == [span]


def test_merging_is_the_same_however_the_ranges_arrive() -> None:
    spans = [
        StationRange(Station(200.0), Station(300.0)),
        StationRange(Station(0.0), Station(100.0)),
        StationRange(Station(90.0), Station(210.0)),
    ]
    assert merge_ranges(spans) == merge_ranges(list(reversed(spans)))


def test_subtracting_a_range_from_itself_leaves_nothing() -> None:
    span = StationRange(Station(0.0), Station(100.0))
    assert span.subtract(span) == []


def test_the_pieces_of_a_subtraction_add_up_to_what_is_left() -> None:
    whole = StationRange(Station(0.0), Station(300.0))
    cut = StationRange(Station(100.0), Station(200.0))
    pieces = whole.subtract(cut)
    assert sum(item.length_m for item in pieces) == pytest.approx(200.0)


@pytest.mark.parametrize("metres", [1e-9, 1.0, 1e6])
def test_a_station_never_loses_its_sign_through_formatting(metres: float) -> None:
    assert Station(-metres).format().startswith("-")
    assert not Station(metres).format().startswith("-")


def test_a_station_of_nothing_is_not_negative() -> None:
    assert Station(0.0).format() == "0+00.00"
    assert Station(-0.0).format() == "0+00.00"


@pytest.mark.parametrize("share", [0.0, 0.5, 1.0])
def test_a_percentile_between_the_ends_is_between_the_values(share: float) -> None:
    import datetime as dt

    from dropcell.interference.stray import StrayCurrentLog

    log = StrayCurrentLog(
        test_point_code="TP-1",
        started_at=dt.datetime(2025, 3, 14, 6, 0),
        sample_interval_s=60.0,
        samples_mv=(-1000.0, -900.0, -800.0),
    )
    value = log.percentile_mv(share)
    assert log.most_negative_mv <= value <= log.most_positive_mv


def test_the_wenner_formula_is_monotonic_in_both_arguments() -> None:
    from dropcell.soil import wenner_resistivity_ohm_m

    assert wenner_resistivity_ohm_m(2.0, 4.0) > wenner_resistivity_ohm_m(1.0, 4.0)
    assert wenner_resistivity_ohm_m(1.0, 8.0) > wenner_resistivity_ohm_m(1.0, 4.0)
    assert wenner_resistivity_ohm_m(1.0, 1.0) == pytest.approx(2 * math.pi)
