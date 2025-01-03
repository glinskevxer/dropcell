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


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
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
        "under criterion",
    )


def test_an_order_can_be_raised_and_listed(run: Callable[..., Result]) -> None:
    seed(run)
    raised = run(
        "work",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "excavation",
        "--summary",
        "dig and recoat",
        "--finding",
        "F-2025-001",
    )
    assert raised.exit_code == 0
    assert "WO-2025-001 raised against 1 findings" in raised.output
    assert "breaks ground" in raised.output
    listed = run("work", "list", "--line", "AL-2")
    assert "WO-2025-001" in listed.output


def test_a_survey_order_does_not_warn_about_breaking_ground(
    run: Callable[..., Result],
) -> None:
    seed(run)
    raised = run(
        "work", "raise", "--line", "AL-2", "--kind", "survey", "--summary", "walk the line"
    )
    assert "breaks ground" not in raised.output


def test_an_order_against_a_finding_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    seed(run)
    result = run(
        "work",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "excavation",
        "--summary",
        "dig",
        "--finding",
        "F-2025-999",
    )
    assert result.exit_code == 3


def test_orders_number_on_within_a_year(run: Callable[..., Result]) -> None:
    seed(run)
    run("work", "raise", "--line", "AL-2", "--kind", "survey", "--summary", "a")
    second = run("work", "raise", "--line", "AL-2", "--kind", "survey", "--summary", "b")
    assert "WO-2025-002" in second.output


def test_an_order_can_be_worked_through_to_done(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "work",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "excavation",
        "--summary",
        "dig",
        "--finding",
        "F-2025-001",
        "--estimate",
        "4200",
    )
    assert "issued" in run("work", "issue", "WO-2025-001").output
    assert "in progress" in run("work", "start", "WO-2025-001").output
    done = run("work", "done", "WO-2025-001", "--cost", "4600")
    assert "finished on 2025-03-14" in done.output
    assert "+400 against an estimate of 4200" in done.output


def test_finishing_an_order_says_the_findings_stay_open(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run(
        "work",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "excavation",
        "--summary",
        "dig",
        "--finding",
        "F-2025-001",
    )
    run("work", "issue", "WO-2025-001")
    done = run("work", "done", "WO-2025-001")
    assert "stay open until a reading proves the work took" in done.output
    assert "F-2025-001" in run("report", "exceptions").output


def test_a_finished_survey_order_says_nothing_about_a_reread(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("work", "raise", "--line", "AL-2", "--kind", "survey", "--summary", "walk")
    run("work", "issue", "WO-2025-001")
    done = run("work", "done", "WO-2025-001")
    assert "stay open" not in done.output


def test_a_forbidden_transition_is_a_conflict(run: Callable[..., Result]) -> None:
    seed(run)
    run("work", "raise", "--line", "AL-2", "--kind", "survey", "--summary", "walk")
    assert run("work", "done", "WO-2025-001").exit_code == 4


def test_an_order_can_be_cancelled_and_drops_off_the_live_list(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("work", "raise", "--line", "AL-2", "--kind", "survey", "--summary", "walk")
    assert "cancelled" in run("work", "cancel", "WO-2025-001").output
    assert "no work orders" in run("work", "list", "--line", "AL-2", "--open").output
    assert "WO-2025-001" in run("work", "list", "--line", "AL-2").output


def test_showing_an_order_lists_its_findings(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "work",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "excavation",
        "--summary",
        "dig",
        "--finding",
        "F-2025-001",
        "--contractor",
        "Bright",
    )
    shown = run("work", "show", "WO-2025-001")
    assert "Bright" in shown.output
    assert "F-2025-001" in shown.output
    assert "under criterion" in shown.output


def test_an_order_with_no_findings_says_so(run: Callable[..., Result]) -> None:
    seed(run)
    run("work", "raise", "--line", "AL-2", "--kind", "survey", "--summary", "walk")
    assert "no findings on this order" in run("work", "show", "WO-2025-001").output


def test_showing_an_order_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("work", "show", "WO-2025-009").exit_code == 3


def test_a_line_with_no_orders_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "no work orders on this line" in run("work", "list", "--line", "AL-2").output
