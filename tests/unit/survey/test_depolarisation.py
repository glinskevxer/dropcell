from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.survey.depolarisation import DepolarisationPoint, DepolarisationSurvey

OFF_AT = dt.datetime(2025, 3, 14, 6, 0)


def point(code: str, off: float, depol: float | None) -> DepolarisationPoint:
    return DepolarisationPoint(test_point_code=code, off_mv=off, depolarised_mv=depol)


def survey(*points: DepolarisationPoint, hours: float = 24.0) -> DepolarisationSurvey:
    return DepolarisationSurvey(
        line_code="AL-2",
        switched_off_at=OFF_AT,
        read_back_at=OFF_AT + dt.timedelta(hours=hours),
        points=points,
    )


def test_a_point_reports_its_drift() -> None:
    assert point("TP-1", -905.0, -780.0).decay_mv == pytest.approx(125.0)


def test_a_point_read_once_has_no_drift() -> None:
    only_once = point("TP-1", -905.0, None)
    assert only_once.decay_mv is None
    assert not only_once.read_twice
    assert only_once.meets() is None


def test_the_criterion_is_a_hundred_millivolts() -> None:
    assert point("TP-1", -905.0, -805.0).meets() is True
    assert point("TP-1", -905.0, -806.0).meets() is False


def test_the_criterion_can_be_tightened() -> None:
    assert point("TP-1", -905.0, -780.0).meets(150.0) is False


def test_an_impossible_potential_is_refused() -> None:
    with pytest.raises(ValidationError):
        point("TP-1", -9000.0, None)
    with pytest.raises(ValidationError):
        point("TP-1", -905.0, 4000.0)


def test_a_survey_read_back_before_the_switch_off_is_refused() -> None:
    with pytest.raises(ValidationError):
        DepolarisationSurvey(
            line_code="AL-2",
            switched_off_at=OFF_AT,
            read_back_at=OFF_AT,
            points=(point("TP-1", -905.0, -780.0),),
        )


def test_a_survey_with_no_posts_is_refused() -> None:
    with pytest.raises(ValidationError):
        survey()


def test_the_same_post_twice_in_one_survey_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        survey(point("TP-1", -905.0, -780.0), point("TP-1", -900.0, -770.0))
    assert caught.value.detail["test_point_code"] == "TP-1"


def test_the_hours_off_come_off_the_two_timestamps() -> None:
    assert survey(point("TP-1", -905.0, -780.0), hours=6.5).hours_off == pytest.approx(6.5)


def test_a_short_survey_is_not_long_enough_to_be_decay() -> None:
    short = survey(point("TP-1", -905.0, -780.0), hours=0.5)
    assert not short.long_enough
    assert not short.fully_depolarised
    assert "not long enough" in short.problems()[0]


def test_a_survey_past_the_minimum_but_under_a_day_says_so() -> None:
    partial = survey(point("TP-1", -905.0, -780.0), hours=4.0)
    assert partial.long_enough
    assert not partial.fully_depolarised
    assert "short of the full period" in partial.problems()[0]


def test_a_full_survey_has_nothing_to_report_about_itself() -> None:
    full = survey(point("TP-1", -905.0, -780.0))
    assert full.fully_depolarised
    assert full.problems() == ()


def test_posts_missed_on_the_way_back_are_named() -> None:
    walked = survey(point("TP-1", -905.0, -780.0), point("TP-2", -900.0, None))
    assert walked.missed_on_the_second_pass == ("TP-2",)
    assert "1 posts were not read on the second pass" in walked.problems()


def test_only_the_posts_read_twice_are_scored() -> None:
    walked = survey(
        point("TP-1", -905.0, -780.0),
        point("TP-2", -900.0, -880.0),
        point("TP-3", -900.0, None),
    )
    assert len(walked.read_back) == 2
    assert [item.test_point_code for item in walked.meeting()] == ["TP-1"]
    assert [item.test_point_code for item in walked.failing()] == ["TP-2"]
    assert walked.share_meeting() == pytest.approx(0.5)


def test_a_survey_where_nobody_came_back_scores_nothing() -> None:
    walked = survey(point("TP-1", -905.0, None))
    assert walked.read_back == ()
    assert walked.share_meeting() == pytest.approx(0.0)


def test_the_line_code_is_normalised() -> None:
    walked = DepolarisationSurvey(
        line_code="al 2",
        switched_off_at=OFF_AT,
        read_back_at=OFF_AT + dt.timedelta(hours=24),
        points=(point("TP-1", -905.0, -780.0),),
    )
    assert walked.line_code == "AL-2"
