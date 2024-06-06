from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import pytest

from dropcell.errors import ValidationError
from dropcell.stationing import Station
from dropcell.survey.cis import CisPoint, CisSurvey
from dropcell.survey.sections import (
    Severity,
    classify_shortfall,
    find_under_criterion,
    total_under_criterion_m,
    worst_section,
)


def survey(offs: Sequence[float | None], step: float = 1.0) -> CisSurvey:
    return CisSurvey(
        line_code="AL-2",
        taken_on=dt.date(2025, 3, 14),
        nominal_interval_m=step,
        points=tuple(
            CisPoint(station=Station(index * step), on_mv=-1120.0, off_mv=off)
            for index, off in enumerate(offs)
        ),
    )


def test_a_walk_that_never_fails_has_no_sections() -> None:
    assert find_under_criterion(survey([-905.0] * 6)) == []


def test_a_single_failing_reading_becomes_one_interval_of_pipe() -> None:
    sections = find_under_criterion(survey([-905.0, -810.0, -905.0]))
    assert len(sections) == 1
    assert sections[0].length_m == pytest.approx(1.0)
    assert sections[0].readings == 1


def test_a_run_of_failures_becomes_one_section() -> None:
    sections = find_under_criterion(survey([-905.0, -810.0, -800.0, -790.0, -905.0]))
    assert len(sections) == 1
    assert sections[0].readings == 3
    assert sections[0].length_m == pytest.approx(3.0)


def test_two_runs_with_good_pipe_between_are_two_sections() -> None:
    offs = [-810.0, -905.0, -905.0, -905.0, -905.0, -800.0]
    assert len(find_under_criterion(survey(offs))) == 2


def test_a_short_run_of_good_readings_can_be_bridged() -> None:
    offs = [-810.0, -905.0, -800.0]
    joined = find_under_criterion(survey(offs), gap_tolerance_m=2.0)
    assert len(joined) == 1
    assert joined[0].readings == 2


def test_bridging_averages_the_two_runs_by_their_reading_counts() -> None:
    offs = [-800.0, -800.0, -905.0, -840.0]
    joined = find_under_criterion(survey(offs), gap_tolerance_m=2.0)
    assert joined[0].mean_off_mv == pytest.approx((-800.0 - 800.0 - 840.0) / 3)


def test_bridging_keeps_the_worst_reading_of_either_run() -> None:
    offs = [-849.0, -905.0, -700.0]
    joined = find_under_criterion(survey(offs), gap_tolerance_m=2.0)
    assert joined[0].worst_off_mv == pytest.approx(-700.0)


def test_a_gap_wider_than_the_tolerance_is_not_bridged() -> None:
    offs = [-810.0, -905.0, -905.0, -905.0, -800.0]
    assert len(find_under_criterion(survey(offs), gap_tolerance_m=2.0)) == 2


def test_a_missing_off_reading_breaks_a_run_without_joining_it() -> None:
    offs: Sequence[float | None] = [-810.0, None, -800.0]
    sections = find_under_criterion(survey(offs))
    assert len(sections) == 2
    assert all(section.readings == 1 for section in sections)


def test_a_missing_off_reading_is_never_itself_a_failure() -> None:
    offs: Sequence[float | None] = [-905.0, None, -905.0]
    assert find_under_criterion(survey(offs)) == []


def test_a_reading_exactly_on_the_threshold_passes() -> None:
    assert find_under_criterion(survey([-850.0, -850.0])) == []


def test_the_threshold_can_be_moved() -> None:
    sections = find_under_criterion(survey([-905.0, -905.0]), threshold_mv=-950.0)
    assert len(sections) == 1


def test_short_sections_can_be_filtered_out() -> None:
    offs = [-905.0, -810.0, -905.0, -800.0, -800.0, -800.0, -905.0]
    kept = find_under_criterion(survey(offs), minimum_length_m=2.0)
    assert len(kept) == 1
    assert kept[0].readings == 3


def test_negative_tolerances_are_refused() -> None:
    with pytest.raises(ValidationError):
        find_under_criterion(survey([-810.0, -810.0]), gap_tolerance_m=-1.0)
    with pytest.raises(ValidationError):
        find_under_criterion(survey([-810.0, -810.0]), minimum_length_m=-1.0)


def test_a_section_reports_its_shortfall_both_ways() -> None:
    section = find_under_criterion(survey([-800.0, -840.0]))[0]
    assert section.worst_shortfall_mv == pytest.approx(50.0)
    assert section.mean_shortfall_mv == pytest.approx(30.0)


@pytest.mark.parametrize(
    ("shortfall", "band"),
    [
        (0.0, Severity.MINOR),
        (24.9, Severity.MINOR),
        (25.0, Severity.MODERATE),
        (74.9, Severity.MODERATE),
        (75.0, Severity.SEVERE),
        (400.0, Severity.SEVERE),
    ],
)
def test_the_severity_bands_are_closed_at_the_bottom(shortfall: float, band: Severity) -> None:
    assert classify_shortfall(shortfall) is band


def test_a_negative_shortfall_is_not_a_shortfall() -> None:
    with pytest.raises(ValidationError):
        classify_shortfall(-4.0)


def test_severity_sorts_worst_last_by_rank() -> None:
    ranks = [band.rank for band in (Severity.MINOR, Severity.MODERATE, Severity.SEVERE)]
    assert ranks == sorted(ranks)


def test_the_total_adds_up_every_section() -> None:
    offs = [-810.0, -905.0, -905.0, -905.0, -800.0]
    sections = find_under_criterion(survey(offs))
    assert total_under_criterion_m(sections) == pytest.approx(2.0)


def test_the_worst_section_is_the_one_with_the_worst_reading() -> None:
    offs = [-810.0, -905.0, -905.0, -905.0, -700.0]
    sections = find_under_criterion(survey(offs))
    found = worst_section(sections)
    assert found is not None
    assert found.worst_off_mv == pytest.approx(-700.0)


def test_there_is_no_worst_section_when_there_are_none() -> None:
    assert worst_section([]) is None
