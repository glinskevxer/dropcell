from __future__ import annotations

from collections.abc import Callable

from click.testing import Result

ADD_LINE = (
    "line",
    "add",
    "AL-2",
    "--name",
    "Ashfield lateral",
    "--operator",
    "Northmoor Gas",
    "--length",
    "18500 m",
    "--diameter",
    "323.9 mm",
    "--installed",
    "1974",
)

RAISE = (
    "finding",
    "raise",
    "--line",
    "AL-2",
    "--kind",
    "under_criterion",
    "--from",
    "39+37.01",
    "--to",
    "41+00.00",
    "--summary",
    "sixty metres under criterion",
)


def test_a_finding_can_be_raised_and_shown(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    raised = run(*RAISE)
    assert raised.exit_code == 0
    assert "F-2025-001 raised on AL-2" in raised.output
    shown = run("finding", "show", "F-2025-001")
    assert "under_criterion" in shown.output
    assert "39+37.01 to 41+00.00" in shown.output
    assert "no date" in shown.output


def test_findings_number_on_within_a_year(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    second = run(*RAISE)
    assert "F-2025-002" in second.output


def test_a_finding_with_no_end_station_is_a_point(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "coating_defect",
        "--from",
        "39+37.01",
        "--summary",
        "category four indication",
    )
    shown = run("finding", "show", "F-2025-001")
    assert "39+37.01 to 39+37.01" in shown.output


def test_raising_against_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run(*RAISE).exit_code == 3


def test_a_due_date_before_the_raised_date_is_a_usage_error(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    result = run(*RAISE, "--due", "2024-01-01")
    assert result.exit_code == 2


def test_raising_opens_the_trail(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE, "--by", "R Ellis")
    shown = run("finding", "show", "F-2025-001")
    assert "Trail" in shown.output
    assert "R Ellis" in shown.output
    assert "raised" in shown.output


def test_a_finding_can_be_scheduled_then_cleared(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    scheduled = run("finding", "schedule", "F-2025-001")
    assert "scheduled" in scheduled.output
    cleared = run("finding", "clear", "F-2025-001", "--by", "J Sowerby")
    assert "cleared on 2025-03-14" in cleared.output
    assert "cleared" in run("report", "exceptions", "--all").output


def test_a_cleared_finding_leaves_the_open_register(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    run("finding", "clear", "F-2025-001", "--by", "J Sowerby")
    assert "no exceptions raised" in run("report", "exceptions").output


def test_accepting_needs_a_reason(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    result = run("finding", "accept", "F-2025-001", "--by", "J Sowerby")
    assert result.exit_code == 2


def test_accepting_with_a_reason_closes_it(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    accepted = run(
        "finding",
        "accept",
        "F-2025-001",
        "--by",
        "J Sowerby",
        "--reason",
        "segment is being replaced",
    )
    assert "accepted by J Sowerby" in accepted.output
    assert "segment is being replaced" in run("finding", "show", "F-2025-001").output


def test_a_cleared_finding_can_be_reopened(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    run("finding", "clear", "F-2025-001", "--by", "J Sowerby")
    reopened = run("finding", "reopen", "F-2025-001")
    assert "reopened" in reopened.output
    assert "F-2025-001" in run("report", "exceptions").output


def test_a_transition_the_state_machine_forbids_is_a_conflict(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    run("finding", "clear", "F-2025-001", "--by", "J Sowerby")
    result = run("finding", "schedule", "F-2025-001")
    assert result.exit_code == 4


def test_moving_a_finding_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    assert run("finding", "clear", "F-2025-001", "--by", "x").exit_code == 3


def test_the_trail_grows_with_every_move(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*RAISE)
    run("finding", "schedule", "F-2025-001")
    run("finding", "clear", "F-2025-001", "--by", "J Sowerby")
    shown = run("finding", "show", "F-2025-001")
    assert shown.output.count("2025-03-14") >= 3
