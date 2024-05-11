from __future__ import annotations

from dropcell.criteria.base import Assessment, Evidence, Outcome, not_assessed
from dropcell.model.enums import CoatingType, ProtectionMethod
from dropcell.model.segment import Segment


def test_only_a_met_outcome_proves_protection() -> None:
    assert Outcome.MET.is_evidence_of_protection
    assert not Outcome.NOT_MET.is_evidence_of_protection
    assert not Outcome.EXCEEDED.is_evidence_of_protection
    assert not Outcome.NOT_ASSESSED.is_evidence_of_protection


def test_a_finding_is_something_that_goes_on_the_register() -> None:
    assert Outcome.NOT_MET.is_a_finding
    assert Outcome.EXCEEDED.is_a_finding
    assert not Outcome.MET.is_a_finding
    assert not Outcome.NOT_ASSESSED.is_a_finding


def test_evidence_borrows_the_coating_and_method_from_its_segment(
    segment: Segment,
) -> None:
    evidence = Evidence(segment=segment, on_mv=-1120.0)
    assert evidence.coating is CoatingType.COAL_TAR
    assert evidence.protection is ProtectionMethod.IMPRESSED_CURRENT


def test_missing_names_the_measurements_that_are_not_there(segment: Segment) -> None:
    evidence = Evidence(segment=segment, on_mv=-1120.0)
    assert evidence.missing("on_mv") == []
    assert evidence.missing("off_mv", "native_mv") == ["off_mv", "native_mv"]
    assert evidence.missing("on_mv", "off_mv") == ["off_mv"]


def test_evidence_defaults_to_nothing_measured(segment: Segment) -> None:
    evidence = Evidence(segment=segment)
    assert evidence.on_mv is None
    assert not evidence.interrupted
    assert evidence.label == ""


def test_an_assessment_knows_whether_it_was_met_and_whether_it_ran() -> None:
    met = Assessment("polarised", Outcome.MET, margin_mv=55.0)
    assert met.met
    assert met.assessed
    missed = Assessment("polarised", Outcome.NOT_MET, margin_mv=-12.0)
    assert not missed.met
    assert missed.assessed
    skipped = Assessment("polarised", Outcome.NOT_ASSESSED)
    assert not skipped.met
    assert not skipped.assessed


def test_flattening_an_assessment_merges_its_detail() -> None:
    assessment = Assessment(
        "polarised",
        Outcome.NOT_MET,
        margin_mv=-12.0,
        note="short of criterion",
        detail={"threshold_mv": -850.0},
    )
    assert assessment.as_dict() == {
        "criterion": "polarised",
        "outcome": "not_met",
        "margin_mv": -12.0,
        "note": "short of criterion",
        "threshold_mv": -850.0,
    }


def test_the_not_assessed_helper_names_what_was_missing() -> None:
    assessment = not_assessed("polarised", ["off_mv"])
    assert assessment.outcome is Outcome.NOT_ASSESSED
    assert assessment.detail["missing"] == ["off_mv"]
    assert "off_mv" in assessment.note


def test_the_not_assessed_helper_copes_with_nothing_at_all() -> None:
    assessment = not_assessed("polarised", [])
    assert assessment.note == "no evidence"


def test_two_assessments_with_the_same_content_are_equal() -> None:
    first = Assessment("polarised", Outcome.MET, margin_mv=55.0)
    second = Assessment("polarised", Outcome.MET, margin_mv=55.0)
    assert first == second
