from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.findings.work import WorkKind, WorkOrder, WorkState

RAISED = dt.date(2025, 3, 14)


def order(**overrides: object) -> WorkOrder:
    kwargs: dict[str, object] = {
        "code": "WO-2025-004",
        "line_code": "AL-2",
        "kind": WorkKind.EXCAVATION,
        "raised_on": RAISED,
        "finding_codes": ("F-2025-001",),
        "summary": "dig and recoat at the beck crossing",
    }
    kwargs.update(overrides)
    return WorkOrder(**kwargs)  # type: ignore[arg-type]


def test_codes_are_normalised_and_sorted() -> None:
    made = order(code="wo 2025 004", finding_codes=("f-2025-002", "F-2025-001"))
    assert made.code == "WO-2025-004"
    assert made.finding_codes == ("F-2025-001", "F-2025-002")


def test_duplicate_finding_codes_count_once() -> None:
    assert order(finding_codes=("F-2025-001", "f 2025 001")).findings == 1


def test_a_job_with_no_summary_is_refused() -> None:
    with pytest.raises(ValidationError):
        order(summary="  ")


def test_a_job_planned_before_it_was_raised_is_refused() -> None:
    with pytest.raises(ValidationError):
        order(planned_for=dt.date(2025, 1, 1))


def test_a_job_planned_on_the_day_it_was_raised_is_fine() -> None:
    assert order(planned_for=RAISED).planned_for == RAISED


def test_only_a_finished_job_carries_a_completion_date() -> None:
    with pytest.raises(ValidationError):
        order(completed_on=dt.date(2025, 5, 1))


def test_a_finished_job_needs_one() -> None:
    with pytest.raises(ValidationError):
        order(state=WorkState.DONE)


def test_a_job_cannot_finish_before_it_was_raised() -> None:
    with pytest.raises(ValidationError):
        order(state=WorkState.DONE, completed_on=dt.date(2025, 1, 1))


def test_negative_money_is_refused() -> None:
    with pytest.raises(ValidationError):
        order(estimate=-1.0)
    with pytest.raises(ValidationError):
        order(actual=-1.0)


def test_the_variance_needs_both_numbers() -> None:
    assert order(estimate=4000.0).variance is None
    assert order(actual=4600.0).variance is None
    assert order(estimate=4000.0, actual=4600.0).variance == pytest.approx(600.0)


def test_a_job_knows_which_findings_it_is_against() -> None:
    made = order(finding_codes=("F-2025-001", "F-2025-002"))
    assert made.covers("F-2025-001")
    assert made.covers("f 2025 002")
    assert not made.covers("F-2025-003")


def test_the_jobs_that_break_ground_are_the_ones_with_a_hole() -> None:
    assert WorkKind.EXCAVATION.breaks_ground
    assert WorkKind.ANODE_INSTALL.breaks_ground
    assert not WorkKind.SURVEY.breaks_ground
    assert not WorkKind.RECTIFIER_REPAIR.breaks_ground


def test_only_a_survey_proves_itself() -> None:
    assert not WorkKind.SURVEY.needs_reread
    assert WorkKind.EXCAVATION.needs_reread
    assert WorkKind.BOND_INSTALL.needs_reread


def test_a_draft_job_can_be_issued_or_dropped() -> None:
    draft = order()
    assert draft.can_move_to(WorkState.ISSUED)
    assert draft.can_move_to(WorkState.CANCELLED)
    assert not draft.can_move_to(WorkState.DONE)


def test_an_issued_job_can_go_back_to_draft() -> None:
    assert order(state=WorkState.ISSUED).can_move_to(WorkState.DRAFT)


def test_a_finished_job_goes_nowhere() -> None:
    done = order(state=WorkState.DONE, completed_on=dt.date(2025, 5, 1))
    assert not done.is_open
    for state in WorkState:
        assert not done.can_move_to(state)


def test_a_cancelled_job_can_be_started_again() -> None:
    cancelled = order(state=WorkState.CANCELLED)
    assert not cancelled.is_open
    assert cancelled.can_move_to(WorkState.DRAFT)


def test_only_the_two_closing_states_are_closed() -> None:
    assert WorkState.DONE.is_closed
    assert WorkState.CANCELLED.is_closed
    assert not WorkState.DRAFT.is_closed
    assert not WorkState.IN_PROGRESS.is_closed


def test_notes_stay_out_of_equality() -> None:
    assert order(notes="contractor cancelled twice") == order()
