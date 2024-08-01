from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.stationing import Station, StationRange


def span(start: float = 1200.0, end: float = 1260.0) -> StationRange:
    return StationRange(Station(start), Station(end))


def finding(**overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "code": "F-2025-014",
        "line_code": "AL-2",
        "kind": FindingKind.UNDER_CRITERION,
        "raised_on": dt.date(2025, 3, 14),
        "extent": span(),
        "summary": "sixty metres under criterion at the road crossing",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)  # type: ignore[arg-type]


def test_codes_are_normalised_and_the_summary_is_trimmed() -> None:
    made = finding(code="f 2025 014", line_code="al-2", summary="  short  ")
    assert (made.code, made.line_code) == ("F-2025-014", "AL-2")
    assert made.summary == "short"


def test_a_finding_with_no_summary_is_refused() -> None:
    with pytest.raises(ValidationError):
        finding(summary="   ")


def test_a_finding_carries_its_place_and_its_length() -> None:
    made = finding()
    assert made.station == Station(1200.0)
    assert made.length_m == pytest.approx(60.0)


def test_a_due_date_before_the_raised_date_is_refused() -> None:
    with pytest.raises(ValidationError):
        finding(due_by=dt.date(2025, 3, 1))


def test_a_due_date_on_the_raised_date_is_allowed() -> None:
    assert finding(due_by=dt.date(2025, 3, 14)).due_by == dt.date(2025, 3, 14)


def test_an_open_finding_cannot_carry_a_closing_date() -> None:
    with pytest.raises(ValidationError):
        finding(closed_on=dt.date(2025, 4, 1))


def test_a_cleared_finding_needs_a_closing_date() -> None:
    with pytest.raises(ValidationError):
        finding(state=FindingState.CLEARED)


def test_a_finding_cannot_close_before_it_was_raised() -> None:
    with pytest.raises(ValidationError):
        finding(state=FindingState.CLEARED, closed_on=dt.date(2025, 1, 1))


def test_accepting_a_finding_without_a_reason_is_refused() -> None:
    with pytest.raises(ValidationError):
        finding(state=FindingState.ACCEPTED, closed_on=dt.date(2025, 4, 1))


def test_accepting_a_finding_with_a_reason_is_allowed() -> None:
    accepted = finding(
        state=FindingState.ACCEPTED,
        closed_on=dt.date(2025, 4, 1),
        closed_by="J Sowerby",
        closed_reason="segment is being replaced in the autumn",
    )
    assert accepted.state.is_closed
    assert not accepted.is_open


def test_clearing_needs_no_reason_because_the_reading_is_the_reason() -> None:
    cleared = finding(state=FindingState.CLEARED, closed_on=dt.date(2025, 4, 1))
    assert cleared.state.is_closed


def test_only_the_two_closing_states_are_closed() -> None:
    assert not FindingState.OPEN.is_closed
    assert not FindingState.SCHEDULED.is_closed
    assert FindingState.CLEARED.is_closed
    assert FindingState.ACCEPTED.is_closed


def test_an_open_finding_past_its_date_is_overdue() -> None:
    late = finding(due_by=dt.date(2025, 4, 1))
    assert late.is_overdue(dt.date(2025, 4, 2))
    assert not late.is_overdue(dt.date(2025, 4, 1))


def test_a_closed_finding_is_never_overdue() -> None:
    closed = finding(
        due_by=dt.date(2025, 4, 1),
        state=FindingState.CLEARED,
        closed_on=dt.date(2025, 4, 20),
    )
    assert not closed.is_overdue(dt.date(2026, 1, 1))


def test_a_finding_with_no_date_is_never_overdue() -> None:
    assert not finding().is_overdue(dt.date(2030, 1, 1))


def test_age_stops_counting_when_the_finding_closes() -> None:
    closed = finding(state=FindingState.CLEARED, closed_on=dt.date(2025, 4, 3))
    assert closed.age_days(dt.date(2026, 1, 1)) == 20
    assert finding().age_days(dt.date(2025, 4, 3)) == 20


def test_transitions_from_open_go_anywhere_but_open() -> None:
    open_finding = finding()
    assert open_finding.can_move_to(FindingState.SCHEDULED)
    assert open_finding.can_move_to(FindingState.CLEARED)
    assert open_finding.can_move_to(FindingState.ACCEPTED)
    assert not open_finding.can_move_to(FindingState.OPEN)


def test_a_scheduled_finding_can_go_back_to_open() -> None:
    scheduled = finding(state=FindingState.SCHEDULED)
    assert scheduled.can_move_to(FindingState.OPEN)


def test_a_cleared_finding_can_only_be_reopened() -> None:
    cleared = finding(state=FindingState.CLEARED, closed_on=dt.date(2025, 4, 1))
    assert cleared.can_move_to(FindingState.OPEN)
    assert not cleared.can_move_to(FindingState.SCHEDULED)
    assert not cleared.can_move_to(FindingState.ACCEPTED)


def test_a_missing_survey_is_a_gap_in_the_work_not_the_pipe() -> None:
    assert FindingKind.MISSING_SURVEY.is_measurement_gap
    assert not FindingKind.UNDER_CRITERION.is_measurement_gap


def test_the_source_does_not_take_part_in_equality() -> None:
    assert finding(source="cis-2025-03.csv") == finding()
