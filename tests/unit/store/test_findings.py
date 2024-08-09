from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError, ValidationError
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.line import Line
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository

RAISED = dt.date(2025, 3, 14)


@pytest.fixture
def findings(database: Database, line: Line) -> FindingRepository:
    LineRepository(database).add(line)
    return FindingRepository(database)


def make_finding(**overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "code": "F-2025-014",
        "line_code": "AL-2",
        "kind": FindingKind.UNDER_CRITERION,
        "raised_on": RAISED,
        "extent": StationRange(Station(1200.0), Station(1260.0)),
        "summary": "sixty metres under criterion",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)  # type: ignore[arg-type]


def test_a_finding_survives_a_round_trip(findings: FindingRepository) -> None:
    raised = make_finding(due_by=dt.date(2025, 6, 1), source="cis-2025-03.csv")
    findings.raise_finding(raised)
    assert findings.get("F-2025-014") == raised


def test_raising_a_finding_opens_its_trail(findings: FindingRepository) -> None:
    findings.raise_finding(make_finding(), actor="R Ellis")
    trail = findings.trail("F-2025-014")
    assert len(trail) == 1
    assert trail[0]["from_state"] == "none"
    assert trail[0]["to_state"] == "open"
    assert trail[0]["actor"] == "R Ellis"


def test_the_same_code_cannot_be_raised_twice(findings: FindingRepository) -> None:
    findings.raise_finding(make_finding())
    with pytest.raises(ConflictError):
        findings.raise_finding(make_finding())


def test_a_finding_on_a_line_that_is_not_there_is_refused(
    findings: FindingRepository,
) -> None:
    with pytest.raises(ConflictError):
        findings.raise_finding(make_finding(line_code="ZZ-9"))


def test_moving_a_finding_writes_the_new_state_and_a_trail_row(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(make_finding())
    moved = findings.move(
        "F-2025-014", FindingState.SCHEDULED, on=dt.date(2025, 3, 20), actor="J Sowerby"
    )
    assert moved.state is FindingState.SCHEDULED
    assert findings.get("F-2025-014").state is FindingState.SCHEDULED
    assert len(findings.trail("F-2025-014")) == 2


def test_clearing_a_finding_stamps_the_date_and_the_name(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(make_finding())
    cleared = findings.move(
        "F-2025-014", FindingState.CLEARED, on=dt.date(2025, 5, 2), actor="R Ellis"
    )
    assert cleared.closed_on == dt.date(2025, 5, 2)
    assert cleared.closed_by == "R Ellis"


def test_accepting_a_finding_without_a_reason_is_refused(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(make_finding())
    with pytest.raises(ValidationError):
        findings.move("F-2025-014", FindingState.ACCEPTED, on=dt.date(2025, 5, 2))


def test_a_transition_the_state_machine_forbids_is_refused(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(make_finding())
    findings.move("F-2025-014", FindingState.CLEARED, on=dt.date(2025, 5, 2))
    with pytest.raises(ConflictError) as caught:
        findings.move("F-2025-014", FindingState.SCHEDULED, on=dt.date(2025, 6, 1))
    assert caught.value.detail["wanted"] == "scheduled"


def test_a_cleared_finding_can_be_reopened(findings: FindingRepository) -> None:
    findings.raise_finding(make_finding())
    findings.move("F-2025-014", FindingState.CLEARED, on=dt.date(2025, 5, 2))
    reopened = findings.move("F-2025-014", FindingState.OPEN, on=dt.date(2025, 9, 1))
    assert reopened.state is FindingState.OPEN
    assert reopened.closed_on is None
    assert len(findings.trail("F-2025-014")) == 3


def test_moving_a_finding_that_is_not_there_is_refused(
    findings: FindingRepository,
) -> None:
    with pytest.raises(NotFoundError):
        findings.move("F-2025-014", FindingState.CLEARED, on=dt.date(2025, 5, 2))


def test_replacing_a_finding_that_is_not_there_is_refused(
    findings: FindingRepository,
) -> None:
    with pytest.raises(NotFoundError):
        findings.replace(make_finding())


def test_the_open_register_leaves_out_closed_findings(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(make_finding())
    findings.raise_finding(make_finding(code="F-2025-015"))
    findings.move("F-2025-015", FindingState.CLEARED, on=dt.date(2025, 5, 2))
    assert [item.code for item in findings.open_findings()] == ["F-2025-014"]


def test_the_open_register_puts_dated_findings_before_undated_ones(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(make_finding(code="F-1"))
    findings.raise_finding(make_finding(code="F-2", due_by=dt.date(2025, 6, 1)))
    assert [item.code for item in findings.open_findings()] == ["F-2", "F-1"]


def test_the_open_register_can_be_narrowed_to_one_line(
    database: Database, findings: FindingRepository, line: Line
) -> None:
    LineRepository(database).add(dataclasses.replace(line, code="BR-9"))
    findings.raise_finding(make_finding(code="F-1"))
    findings.raise_finding(make_finding(code="F-2", line_code="BR-9"))
    assert [item.code for item in findings.open_findings("BR-9")] == ["F-2"]


def test_overdue_findings_are_the_open_ones_past_their_date(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(make_finding(code="F-1", due_by=dt.date(2025, 4, 1)))
    findings.raise_finding(make_finding(code="F-2", due_by=dt.date(2025, 9, 1)))
    late = findings.overdue(dt.date(2025, 6, 1))
    assert [item.code for item in late] == ["F-1"]


def test_findings_for_a_line_come_back_in_stationing_order(
    findings: FindingRepository,
) -> None:
    findings.raise_finding(
        make_finding(code="F-2", extent=StationRange(Station(4000.0), Station(4010.0)))
    )
    findings.raise_finding(make_finding(code="F-1"))
    assert [item.code for item in findings.for_line("AL-2")] == ["F-1", "F-2"]


def test_deleting_a_line_takes_its_findings_and_their_trail(
    database: Database, findings: FindingRepository
) -> None:
    findings.raise_finding(make_finding())
    LineRepository(database).delete("AL-2")
    assert findings.count() == 0
    assert database.scalar("SELECT count(*) FROM finding_event") == 0
