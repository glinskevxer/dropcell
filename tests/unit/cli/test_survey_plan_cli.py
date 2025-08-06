from __future__ import annotations

from collections.abc import Callable

from click.testing import Result


def add_line(run: Callable[..., Result], code: str, length: str) -> None:
    run(
        "line",
        "add",
        code,
        "--name",
        code,
        "--operator",
        "Northmoor Gas",
        "--length",
        length,
        "--diameter",
        "323.9 mm",
        "--installed",
        "1974",
    )


def add_segment(
    run: Callable[..., Result],
    code: str,
    line: str,
    start: str,
    end: str,
    coating: str = "coal_tar",
    protection: str = "impressed_current",
) -> None:
    run(
        "segment",
        "add",
        code,
        "--line",
        line,
        "--from",
        start,
        "--to",
        end,
        "--coating",
        coating,
        "--protection",
        protection,
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1974",
    )


def test_an_empty_register_has_nothing_to_plan(run: Callable[..., Result]) -> None:
    result = run("plan", "survey", "--budget", "10")
    assert result.exit_code == 0
    assert "no segments anywhere" in result.output


def test_a_budget_fills_with_the_worst_pipe(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "0+00.00", "100+00.00")
    add_segment(
        run,
        "AL-2-002",
        "AL-2",
        "100+00.01",
        "200+00.00",
        coating="tape_wrap",
        protection="unprotected",
    )
    result = run("plan", "survey", "--budget", "4")
    assert "Survey plan, 4.0 km" in result.output
    assert "walk" in result.output


def test_the_pipe_the_budget_did_not_reach_is_named(
    run: Callable[..., Result],
) -> None:
    add_line(run, "AL-2", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "0+00.00", "100+00.00")
    add_segment(
        run,
        "AL-2-002",
        "AL-2",
        "100+00.01",
        "200+00.00",
        coating="tape_wrap",
        protection="unprotected",
    )
    result = run("plan", "survey", "--budget", "3.1")
    assert "not reached" in result.output
    assert "walking everything at least that bad needs" in result.output


def test_a_budget_that_covers_everything_leaves_nothing_unreached(
    run: Callable[..., Result],
) -> None:
    add_line(run, "AL-2", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "0+00.00", "100+00.00")
    result = run("plan", "survey", "--budget", "100")
    assert "not reached" not in result.output
    assert "km of budget unspent" in result.output


def test_the_plan_can_be_narrowed_to_one_line(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "18500 m")
    add_line(run, "BR-9", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "0+00.00", "100+00.00")
    add_segment(run, "BR-9-001", "BR-9", "0+00.00", "100+00.00")
    result = run("plan", "survey", "--budget", "100", "--line", "AL-2")
    assert "AL-2-001" in result.output
    assert "BR-9-001" not in result.output


def test_a_retired_line_is_left_out_of_the_estate_plan(
    run: Callable[..., Result],
) -> None:
    add_line(run, "AL-2", "18500 m")
    add_line(run, "BR-9", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "0+00.00", "100+00.00")
    add_segment(run, "BR-9-001", "BR-9", "0+00.00", "100+00.00")
    run("line", "retire", "BR-9")
    result = run("plan", "survey", "--budget", "100")
    assert "AL-2-001" in result.output
    assert "BR-9-001" not in result.output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("plan", "survey", "--budget", "10", "--line", "ZZ-9").exit_code == 3
