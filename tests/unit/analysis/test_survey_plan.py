from __future__ import annotations

import pytest

from dropcell.analysis.risk import SegmentRisk
from dropcell.analysis.survey_plan import budget_for, plan_surveys
from dropcell.errors import ValidationError


def risk(code: str, score: float, length_m: float) -> SegmentRisk:
    return SegmentRisk(segment_code=code, length_m=length_m, score=score, terms=())


def owners(*codes: str) -> dict[str, str]:
    return {code: "AL-2" for code in codes}


def test_an_empty_budget_walks_nothing() -> None:
    plan = plan_surveys([risk("A", 5.0, 1000.0)], owners("A"), budget_km=0.0)
    assert plan.walking == ()
    assert [item.segment_code for item in plan.skipped] == ["A"]


def test_a_negative_budget_is_refused() -> None:
    with pytest.raises(ValidationError):
        plan_surveys([], {}, budget_km=-1.0)


def test_the_worst_segment_is_walked_first() -> None:
    scores = [risk("A", 2.0, 1000.0), risk("B", 9.0, 1000.0)]
    plan = plan_surveys(scores, owners("A", "B"), budget_km=1.0)
    assert [item.segment_code for item in plan.walking] == ["B"]


def test_the_budget_is_filled_until_it_runs_out() -> None:
    scores = [risk("A", 9.0, 2000.0), risk("B", 5.0, 2000.0), risk("C", 1.0, 2000.0)]
    plan = plan_surveys(scores, owners("A", "B", "C"), budget_km=4.0)
    assert [item.segment_code for item in plan.walking] == ["A", "B"]
    assert [item.segment_code for item in plan.skipped] == ["C"]


def test_a_segment_that_does_not_fit_is_skipped_rather_than_part_walked() -> None:
    scores = [risk("A", 9.0, 5000.0), risk("B", 5.0, 1000.0)]
    plan = plan_surveys(scores, owners("A", "B"), budget_km=2.0)
    assert [item.segment_code for item in plan.walking] == ["B"]
    assert plan.planned_km == pytest.approx(1.0)


def test_a_long_mild_segment_does_not_crowd_out_a_short_bad_one() -> None:
    scores = [risk("long", 2.0, 20000.0), risk("short", 9.0, 500.0)]
    plan = plan_surveys(scores, owners("long", "short"), budget_km=1.0)
    assert [item.segment_code for item in plan.walking] == ["short"]


def test_the_plan_reports_what_it_used_and_what_is_left() -> None:
    plan = plan_surveys([risk("A", 9.0, 1500.0)], owners("A"), budget_km=4.0)
    assert plan.planned_km == pytest.approx(1.5)
    assert plan.spare_km == pytest.approx(2.5)


def test_a_full_budget_leaves_nothing_spare() -> None:
    plan = plan_surveys([risk("A", 9.0, 4000.0)], owners("A"), budget_km=4.0)
    assert plan.spare_km == pytest.approx(0.0)


def test_the_skipped_kilometres_are_counted() -> None:
    scores = [risk("A", 9.0, 1000.0), risk("B", 5.0, 3000.0)]
    plan = plan_surveys(scores, owners("A", "B"), budget_km=1.0)
    assert plan.skipped_km == pytest.approx(3.0)


def test_the_worst_skipped_is_the_argument_for_more_budget() -> None:
    scores = [risk("A", 9.0, 1000.0), risk("B", 8.0, 3000.0), risk("C", 1.0, 3000.0)]
    plan = plan_surveys(scores, owners("A", "B", "C"), budget_km=1.0)
    worst = plan.worst_skipped
    assert worst is not None
    assert worst.segment_code == "B"


def test_a_plan_that_reached_everything_has_no_worst_skipped() -> None:
    plan = plan_surveys([risk("A", 9.0, 1000.0)], owners("A"), budget_km=4.0)
    assert plan.worst_skipped is None
    assert "not reached" not in plan.summary()


def test_the_summary_names_the_budget_and_what_it_bought() -> None:
    scores = [risk("A", 9.0, 1000.0), risk("B", 5.0, 3000.0)]
    text = plan_surveys(scores, owners("A", "B"), budget_km=1.0).summary()
    assert "1 segments, 1.0 km of 1.0 km budgeted" in text
    assert "3.0 km not reached" in text


def test_the_line_a_segment_belongs_to_travels_with_it() -> None:
    plan = plan_surveys([risk("A", 9.0, 1000.0)], {"A": "BR-9"}, budget_km=4.0)
    assert plan.walking[0].line_code == "BR-9"


def test_a_segment_with_no_known_line_still_plans() -> None:
    plan = plan_surveys([risk("A", 9.0, 1000.0)], {}, budget_km=4.0)
    assert plan.walking[0].line_code == ""


def test_the_budget_needed_for_a_threshold_is_the_other_direction() -> None:
    scores = [risk("A", 9.0, 1000.0), risk("B", 5.0, 3000.0), risk("C", 1.0, 3000.0)]
    assert budget_for(scores, above_score=5.0) == pytest.approx(4.0)
    assert budget_for(scores, above_score=9.0) == pytest.approx(1.0)
    assert budget_for(scores, above_score=0.0) == pytest.approx(7.0)


def test_a_negative_threshold_is_refused() -> None:
    with pytest.raises(ValidationError):
        budget_for([], above_score=-1.0)
