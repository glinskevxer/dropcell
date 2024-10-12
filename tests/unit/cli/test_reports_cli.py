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

ADD_SEGMENT = (
    "segment",
    "add",
    "AL-2-004",
    "--line",
    "AL-2",
    "--from",
    "0+00.00",
    "--to",
    "39+37.01",
    "--coating",
    "coal_tar",
    "--diameter",
    "323.9 mm",
    "--wall",
    "6.35 mm",
    "--installed",
    "1974",
)


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post",
        "add",
        "TP-114",
        "--line",
        "AL-2",
        "--at",
        "10+00.00",
        "--installed",
        "1998-05-04",
    )


def test_protection_reports_a_protected_post(run: Callable[..., Result]) -> None:
    seed(run)
    run("post", "read", "TP-114", "--on", "-1120", "--off", "-905")
    printed = run("report", "protection", "--line", "AL-2")
    assert printed.exit_code == 0
    assert "Protection, AL-2" in printed.output
    assert "protection rate 100.0%" in printed.output


def test_protection_on_a_line_with_no_posts_exits_three(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    assert run("report", "protection", "--line", "AL-2").exit_code == 3


def test_protection_on_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("report", "protection", "--line", "ZZ-9").exit_code == 3


def test_exceptions_on_an_empty_register_says_so(run: Callable[..., Result]) -> None:
    printed = run("report", "exceptions")
    assert printed.exit_code == 0
    assert "no exceptions raised" in printed.output


def test_exceptions_can_be_narrowed_to_a_line(run: Callable[..., Result]) -> None:
    seed(run)
    printed = run("report", "exceptions", "--line", "AL-2")
    assert "Exception register, AL-2" in printed.output


def test_exceptions_for_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("report", "exceptions", "--line", "ZZ-9").exit_code == 3


def test_compliance_reports_the_posts_and_their_rules(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("post", "read", "TP-114", "--on", "-1120", "--date", "2024-12-01")
    printed = run("report", "compliance", "--line", "AL-2")
    assert "Monitoring compliance, AL-2" in printed.output
    assert "test_point_annual" in printed.output or "1 asset and rule pairs" in printed.output


def test_a_post_never_read_shows_up_as_overdue(run: Callable[..., Result]) -> None:
    seed(run)
    printed = run("report", "compliance", "--line", "AL-2")
    assert "TP-114" in printed.output
    assert "never" in printed.output


def test_a_post_installed_recently_is_not_overdue(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post", "add", "TP-9", "--line", "AL-2", "--at", "10+00.00", "--installed", "2025-02-01"
    )
    printed = run("report", "compliance", "--line", "AL-2")
    assert "nothing overdue" in printed.output


def test_the_compliance_window_can_be_widened(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post", "add", "TP-9", "--line", "AL-2", "--at", "10+00.00", "--installed", "2025-02-01"
    )
    narrow = run("report", "compliance", "--line", "AL-2", "--window", "1")
    wide = run("report", "compliance", "--line", "AL-2", "--window", "900")
    assert "nothing due in the window" in narrow.output
    assert "TP-9" in wide.output


def test_coverage_reports_the_share_within_reach(run: Callable[..., Result]) -> None:
    seed(run)
    printed = run("report", "coverage", "--line", "AL-2")
    assert "Coverage, AL-2" in printed.output
    assert "1 posts over 18500 m" in printed.output
    assert "Gaps" in printed.output


def test_coverage_names_segments_with_no_post(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post",
        "add",
        "TP-9",
        "--line",
        "AL-2",
        "--at",
        "180+00.00",
        "--installed",
        "1998-05-04",
    )
    printed = run("report", "coverage", "--line", "AL-2")
    assert "segments with no post: AL-2-004" in printed.output


def test_the_reach_can_be_given_in_feet(run: Callable[..., Result]) -> None:
    seed(run)
    printed = run("report", "coverage", "--line", "AL-2", "--reach", "1000 ft")
    assert "within 305 m of a post" in printed.output


def test_a_line_with_two_posts_reports_a_mean_spacing(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run(
        "post",
        "add",
        "TP-115",
        "--line",
        "AL-2",
        "--at",
        "200+00.00",
        "--installed",
        "1998-05-04",
    )
    printed = run("report", "coverage", "--line", "AL-2")
    assert "mean spacing" in printed.output
