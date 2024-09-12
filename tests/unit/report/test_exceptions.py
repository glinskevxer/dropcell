from __future__ import annotations

import datetime as dt

import pytest

from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.report.exceptions import (
    by_kind,
    exception_table,
    order,
    render_exceptions,
    summarise,
)
from dropcell.stationing import Convention, Station, StationRange

TODAY = dt.date(2025, 3, 14)


def finding(**overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "code": "F-2025-001",
        "line_code": "AL-2",
        "kind": FindingKind.UNDER_CRITERION,
        "raised_on": dt.date(2025, 1, 10),
        "extent": StationRange(Station(1200.0), Station(1260.0)),
        "summary": "sixty metres under criterion",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)  # type: ignore[arg-type]


def test_an_empty_register_says_so() -> None:
    rendered = render_exceptions([], as_of=TODAY)
    assert "no exceptions raised" in rendered
    assert "0 findings" in rendered


def test_overdue_findings_come_first() -> None:
    late = finding(code="F-1", due_by=dt.date(2025, 1, 20))
    soon = finding(code="F-2", due_by=dt.date(2025, 4, 1))
    assert [item.code for item in order([soon, late], TODAY)] == ["F-1", "F-2"]


def test_the_worst_overdue_is_at_the_very_top() -> None:
    late = finding(code="F-1", due_by=dt.date(2025, 2, 1))
    later = finding(code="F-2", due_by=dt.date(2025, 1, 12))
    assert [item.code for item in order([late, later], TODAY)] == ["F-2", "F-1"]


def test_undated_findings_go_last() -> None:
    dated = finding(code="F-1", due_by=dt.date(2025, 9, 1))
    undated = finding(code="F-2")
    assert [item.code for item in order([undated, dated], TODAY)] == ["F-1", "F-2"]


def test_findings_due_soonest_come_before_findings_due_later() -> None:
    near = finding(code="F-1", due_by=dt.date(2025, 4, 1))
    far = finding(code="F-2", due_by=dt.date(2025, 9, 1))
    assert [item.code for item in order([far, near], TODAY)] == ["F-1", "F-2"]


def test_ties_are_broken_on_the_code() -> None:
    first = finding(code="F-1", due_by=dt.date(2025, 4, 1))
    second = finding(code="F-2", due_by=dt.date(2025, 4, 1))
    assert [item.code for item in order([second, first], TODAY)] == ["F-1", "F-2"]


def test_a_closed_finding_is_never_treated_as_overdue() -> None:
    closed = finding(
        code="F-1",
        due_by=dt.date(2025, 1, 20),
        state=FindingState.CLEARED,
        closed_on=dt.date(2025, 2, 1),
    )
    open_one = finding(code="F-2", due_by=dt.date(2025, 4, 1))
    assert [item.code for item in order([closed, open_one], TODAY)] == ["F-2", "F-1"]


def test_the_table_carries_a_row_per_finding() -> None:
    table = exception_table([finding(), finding(code="F-2")], as_of=TODAY)
    assert len(table.render().splitlines()) == 6


def test_the_table_prints_stations_in_the_convention_it_was_given() -> None:
    rendered = exception_table([finding()], as_of=TODAY).render()
    assert "39+37.01" in rendered
    metric = exception_table([finding()], as_of=TODAY, convention=Convention.METRIC).render()
    assert "1+200.0" in metric


def test_a_finding_with_no_date_prints_an_empty_due_column() -> None:
    rendered = exception_table([finding()], as_of=TODAY).render()
    assert "under_criterion" in rendered


def test_the_summary_counts_what_is_open_and_what_is_late() -> None:
    findings = [
        finding(code="F-1", due_by=dt.date(2025, 1, 20)),
        finding(code="F-2", due_by=dt.date(2025, 9, 1)),
        finding(
            code="F-3",
            state=FindingState.CLEARED,
            closed_on=dt.date(2025, 2, 1),
        ),
    ]
    summary = summarise(findings, TODAY)
    assert summary.total == 3
    assert summary.open_findings == 2
    assert summary.closed == 1
    assert summary.overdue == 1


def test_the_summary_adds_up_the_pipe() -> None:
    summary = summarise([finding(), finding(code="F-2")], TODAY)
    assert summary.total_length_m == pytest.approx(120.0)
    assert "120 m of pipe" in summary.render()


def test_the_whole_report_carries_the_table_and_the_summary() -> None:
    rendered = render_exceptions([finding()], as_of=TODAY)
    assert "Exception register" in rendered
    assert "1 findings" in rendered


def test_the_title_can_be_changed() -> None:
    rendered = render_exceptions([finding()], as_of=TODAY, title="Open work, AL-2")
    assert rendered.startswith("Open work, AL-2")


def test_grouping_splits_the_register_by_kind() -> None:
    grouped = by_kind([finding(), finding(code="F-2", kind=FindingKind.COATING_DEFECT)])
    assert set(grouped) == {FindingKind.UNDER_CRITERION, FindingKind.COATING_DEFECT}
    assert len(grouped[FindingKind.UNDER_CRITERION]) == 1


def test_grouping_nothing_gives_nothing() -> None:
    assert by_kind([]) == {}
