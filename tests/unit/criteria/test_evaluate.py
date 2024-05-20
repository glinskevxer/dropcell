from __future__ import annotations

import dataclasses

import pytest

from dropcell.criteria.ac import TouchVoltageLimit
from dropcell.criteria.base import Assessment, Evidence, Outcome
from dropcell.criteria.decay import PolarisationDecayCriterion
from dropcell.criteria.evaluate import CriterionSet, PointVerdict
from dropcell.criteria.limits import OverProtectionLimit
from dropcell.criteria.potential import OnPotentialCriterion, PolarisedPotentialCriterion
from dropcell.model.enums import ProtectionMethod
from dropcell.model.segment import Segment

STANDARD = CriterionSet(
    name="standard",
    criteria=(PolarisedPotentialCriterion(), PolarisationDecayCriterion()),
    limits=(OverProtectionLimit(),),
)


def evidence(segment: Segment, **overrides: object) -> Evidence:
    return Evidence(segment=segment, **overrides)  # type: ignore[arg-type]


def verdict(*assessments: Assessment) -> PointVerdict:
    return PointVerdict(label="TP-114", criteria=assessments)


def test_a_point_that_meets_one_criterion_is_protected(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-905.0))
    assert result.protected
    assert [item.criterion for item in result.met] == ["polarised_potential"]


def test_meeting_the_second_criterion_is_enough_on_its_own(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-780.0, depolarised_mv=-600.0))
    assert result.protected
    assert [item.criterion for item in result.failed] == ["polarised_potential"]


def test_a_point_that_meets_nothing_is_not_protected(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-780.0, depolarised_mv=-760.0))
    assert not result.protected
    assert result.has_findings


def test_a_protected_point_that_breaks_a_limit_still_has_a_finding(
    segment: Segment,
) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-1420.0))
    assert result.protected
    assert result.has_findings
    assert [item.criterion for item in result.exceeded] == ["over_protection"]


def test_a_protected_point_inside_every_limit_has_no_findings(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-905.0))
    assert not result.has_findings


def test_a_point_with_nothing_measured_is_not_assessed(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment))
    assert not result.assessed
    assert not result.protected
    assert result.summary().endswith("not assessed")


def test_criteria_that_do_not_apply_are_left_out_entirely(segment: Segment) -> None:
    with_on = CriterionSet(name="both", criteria=(OnPotentialCriterion(),))
    assert with_on.evaluate(evidence(segment, on_mv=-1120.0)).criteria == ()
    galvanic = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    assert len(with_on.evaluate(evidence(galvanic, on_mv=-1120.0)).criteria) == 1


def test_limits_that_do_not_apply_are_left_out_too(segment: Segment) -> None:
    with_touch = CriterionSet(name="ac", limits=(TouchVoltageLimit(),))
    assert with_touch.evaluate(evidence(segment)).limits == ()
    assert with_touch.evaluate(evidence(segment, ac_voltage_v=3.0)).limits


def test_a_limit_that_was_not_broken_is_not_evidence_of_protection(
    segment: Segment,
) -> None:
    only_limits = CriterionSet(name="limits only", limits=(OverProtectionLimit(),))
    result = only_limits.evaluate(evidence(segment, off_mv=-780.0))
    assert result.limits[0].outcome is Outcome.MET
    assert not result.protected
    assert result.has_findings


def test_the_applicable_list_names_what_could_run(segment: Segment) -> None:
    assert [c.key for c in STANDARD.applicable(evidence(segment))] == [
        "polarised_potential",
        "polarisation_decay",
    ]


def test_the_set_lists_its_keys_criteria_first() -> None:
    assert STANDARD.keys == (
        "polarised_potential",
        "polarisation_decay",
        "over_protection",
    )


def test_a_verdict_can_be_looked_up_by_criterion_key(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-905.0))
    found = result.by_key("polarised_potential")
    assert found is not None
    assert found.outcome is Outcome.MET
    assert result.by_key("nothing_like_this") is None


def test_the_best_margin_is_the_widest_pass() -> None:
    result = verdict(
        Assessment("a", Outcome.MET, margin_mv=12.0),
        Assessment("b", Outcome.MET, margin_mv=88.0),
    )
    assert result.best_margin_mv == pytest.approx(88.0)


def test_the_worst_margin_is_the_nearest_miss() -> None:
    result = verdict(
        Assessment("a", Outcome.NOT_MET, margin_mv=-4.0),
        Assessment("b", Outcome.NOT_MET, margin_mv=-91.0),
    )
    assert result.worst_margin_mv == pytest.approx(-4.0)


def test_margins_come_back_as_nothing_when_no_criterion_carried_one() -> None:
    result = verdict(Assessment("a", Outcome.MET))
    assert result.best_margin_mv is None
    assert result.worst_margin_mv is None


def test_unassessed_criteria_are_kept_and_reported(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-905.0))
    assert [item.criterion for item in result.unassessed] == ["polarisation_decay"]


def test_the_summary_names_the_limit_that_was_broken(segment: Segment) -> None:
    result = STANDARD.evaluate(evidence(segment, off_mv=-1420.0))
    assert "over_protection" in result.summary()
    assert "protected" in result.summary()


def test_the_label_falls_back_to_the_segment_code(segment: Segment) -> None:
    assert STANDARD.evaluate(evidence(segment, off_mv=-905.0)).label == "AL-2-004"
    labelled = STANDARD.evaluate(evidence(segment, off_mv=-905.0, label="TP-114"))
    assert labelled.label == "TP-114"
