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
    "AL-2-001",
    "--line",
    "AL-2",
    "--from",
    "0+00.00",
    "--to",
    "600+00.00",
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


def test_a_line_in_hand_asks_for_nobody(run: Callable[..., Result]) -> None:
    run(
        "line",
        "add",
        "SH-1",
        "--name",
        "Short lateral",
        "--operator",
        "Northmoor Gas",
        "--length",
        "1000 m",
        "--diameter",
        "323.9 mm",
        "--installed",
        "1974",
    )
    run(
        "segment",
        "add",
        "SH-1-001",
        "--line",
        "SH-1",
        "--from",
        "0+00.00",
        "--to",
        "32+80.00",
        "--coating",
        "coal_tar",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1974",
    )
    run(
        "post", "add", "TP-1", "--line", "SH-1", "--at", "16+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
    result = run("plan", "next", "--line", "SH-1")
    assert result.exit_code == 0
    assert "nothing on this line is asking for anybody" in result.output


def test_a_line_with_no_posts_at_all_says_nothing_is_measured(
    run: Callable[..., Result],
) -> None:
    seed(run)
    result = run("plan", "next", "--line", "AL-2")
    assert result.exit_code == 0
    assert "has no post within reach" in result.output


def test_a_post_nobody_has_read_is_the_first_thing(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    result = run("plan", "next", "--line", "AL-2")
    assert "TP-1 has never been read" in result.output
    assert "will not wait" in result.output


def test_an_overdue_finding_will_not_wait(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "coating_defect",
        "--from",
        "150+00.00",
        "--summary",
        "category four",
        "--due",
        "2025-01-10",
        today="2025-01-02",
    )
    result = run("plan", "next", "--line", "AL-2")
    assert "F-2025-001" in result.output
    assert "past its date" in result.output


def test_a_finding_still_in_date_is_not_on_the_page(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "coating_defect",
        "--from",
        "150+00.00",
        "--summary",
        "category four",
        "--due",
        "2025-09-01",
    )
    result = run("plan", "next", "--line", "AL-2")
    assert "F-2025-001" not in result.output


def test_a_post_under_criterion_is_on_the_page(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-780")
    result = run("plan", "next", "--line", "AL-2")
    assert "TP-1 is under criterion" in result.output


def test_a_post_read_long_ago_is_on_the_page(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905", "--date", "2022-05-02")
    result = run("plan", "next", "--line", "AL-2")
    assert "was last read" in result.output


def test_a_stretch_with_no_post_is_on_the_page(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
    result = run("plan", "next", "--line", "AL-2")
    assert "has no post within reach" in result.output


def test_the_soonest_things_come_first(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-780")
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "coating_defect",
        "--from",
        "150+00.00",
        "--summary",
        "category four",
        "--due",
        "2025-01-10",
        today="2025-01-02",
    )
    result = run("plan", "next", "--line", "AL-2")
    assert result.output.index("F-2025-001") < result.output.index("under criterion")


def test_the_page_can_be_trimmed(run: Callable[..., Result]) -> None:
    seed(run)
    for index in range(4):
        run(
            "post",
            "add",
            f"TP-{index}",
            "--line",
            "AL-2",
            "--at",
            f"{10 + index * 20}+00.00",
            "--installed",
            "1998-05-04",
        )
    trimmed = run("plan", "next", "--line", "AL-2", "--limit", "2")
    assert trimmed.output.count("has never been read") == 2


def test_the_page_says_the_ranking_is_the_point(run: Callable[..., Result]) -> None:
    seed(run)
    assert "the ranking is the point" in run("plan", "next", "--line", "AL-2").output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("plan", "next", "--line", "ZZ-9").exit_code == 3
