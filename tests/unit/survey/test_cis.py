from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.stationing import Station, StationRange
from dropcell.survey.cis import CisPoint, CisSurvey


def point(station: float, on_mv: float = -1120.0, off_mv: float | None = -905.0) -> CisPoint:
    return CisPoint(station=Station(station), on_mv=on_mv, off_mv=off_mv)


def survey(*points: CisPoint, **overrides: object) -> CisSurvey:
    kwargs: dict[str, object] = {
        "line_code": "AL-2",
        "taken_on": dt.date(2025, 3, 14),
        "points": points,
    }
    kwargs.update(overrides)
    return CisSurvey(**kwargs)  # type: ignore[arg-type]


def walk(count: int, step: float = 1.5, off_mv: float = -905.0) -> list[CisPoint]:
    return [point(index * step, off_mv=off_mv) for index in range(count)]


def test_a_survey_keeps_its_points_in_stationing_order() -> None:
    walked = survey(point(3.0), point(0.0), point(1.5))
    assert [item.station.metres for item in walked.points] == [0.0, 1.5, 3.0]


def test_one_step_is_not_a_survey() -> None:
    with pytest.raises(ValidationError):
        survey(point(0.0))


def test_two_readings_at_the_same_station_are_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        survey(point(0.0), point(1.5), point(1.5))
    assert caught.value.detail["station_m"] == pytest.approx(1.5)


def test_a_nominal_interval_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        survey(*walk(3), nominal_interval_m=0.0)


def test_the_line_code_is_normalised() -> None:
    assert survey(*walk(3), line_code="al 2").line_code == "AL-2"


def test_the_extent_runs_from_the_first_step_to_the_last() -> None:
    walked = survey(*walk(5))
    assert walked.extent == StationRange(Station(0.0), Station(6.0))
    assert walked.length_m == pytest.approx(6.0)


def test_a_point_knows_its_own_ir_drop() -> None:
    assert point(0.0).ir_drop_mv == pytest.approx(-215.0)
    assert point(0.0, off_mv=None).ir_drop_mv is None
    assert not point(0.0, off_mv=None).has_off


def test_a_point_refuses_an_impossible_potential() -> None:
    with pytest.raises(ValidationError):
        point(0.0, on_mv=-9000.0)
    with pytest.raises(ValidationError):
        point(0.0, off_mv=-9000.0)


def test_interruption_coverage_counts_the_steps_that_caught_an_off() -> None:
    walked = survey(point(0.0), point(1.5, off_mv=None), point(3.0), point(4.5))
    assert walked.interruption_coverage == pytest.approx(0.75)
    assert len(walked.interrupted_points) == 3


def test_a_survey_with_no_off_readings_has_no_statistics() -> None:
    walked = survey(point(0.0, off_mv=None), point(1.5, off_mv=None))
    assert walked.mean_off_mv is None
    assert walked.most_positive_off_mv is None
    assert walked.most_negative_off_mv is None
    assert walked.interruption_coverage == pytest.approx(0.0)


def test_the_statistics_describe_the_off_trace() -> None:
    walked = survey(
        point(0.0, off_mv=-900.0), point(1.5, off_mv=-800.0), point(3.0, off_mv=-1000.0)
    )
    assert walked.mean_off_mv == pytest.approx(-900.0)
    assert walked.most_positive_off_mv == pytest.approx(-800.0)
    assert walked.most_negative_off_mv == pytest.approx(-1000.0)


def test_spacings_are_the_distances_between_consecutive_steps() -> None:
    walked = survey(point(0.0), point(1.5), point(4.5))
    assert walked.spacings_m() == pytest.approx([1.5, 3.0])


def test_an_ordinary_walk_has_no_gaps() -> None:
    assert survey(*walk(6)).gaps() == []


def test_a_long_step_is_ground_the_crew_could_not_get_onto() -> None:
    walked = survey(point(0.0), point(1.5), point(60.0), point(61.5))
    assert walked.gaps() == [StationRange(Station(1.5), Station(60.0))]


def test_the_gap_multiple_can_be_tightened() -> None:
    walked = survey(point(0.0), point(1.5), point(6.0))
    assert walked.gaps() == []
    assert len(walked.gaps(multiple=2.0)) == 1


def test_a_gap_multiple_of_one_or_less_makes_no_sense() -> None:
    with pytest.raises(ValidationError):
        survey(*walk(3)).gaps(multiple=1.0)


def test_points_in_a_range_are_the_ones_inside_it() -> None:
    walked = survey(*walk(6))
    inside = walked.points_in(StationRange(Station(1.5), Station(4.5)))
    assert [item.station.metres for item in inside] == [1.5, 3.0, 4.5]


def test_the_nearest_step_to_a_post_is_the_closest_one() -> None:
    walked = survey(*walk(6))
    assert walked.nearest(Station(4.2)).station.metres == pytest.approx(4.5)
    assert walked.nearest(Station(-40.0)).station.metres == pytest.approx(0.0)
    assert walked.nearest(Station(400.0)).station.metres == pytest.approx(7.5)
