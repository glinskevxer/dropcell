from __future__ import annotations

from collections.abc import Callable

from click.testing import Result


def add_line(run: Callable[..., Result], code: str, name: str, length: str) -> None:
    run(
        "line",
        "add",
        code,
        "--name",
        name,
        "--operator",
        "Northmoor Gas",
        "--length",
        length,
        "--diameter",
        "323.9 mm",
        "--installed",
        "1974",
    )


def add_segment(run: Callable[..., Result], code: str, line: str, to_station: str) -> None:
    run(
        "segment",
        "add",
        code,
        "--line",
        line,
        "--from",
        "0+00.00",
        "--to",
        to_station,
        "--coating",
        "coal_tar",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1974",
    )


def test_an_empty_register_says_so(run: Callable[..., Result]) -> None:
    result = run("plan", "estate")
    assert result.exit_code == 0
    assert "no lines in the register" in result.output


def test_a_line_with_no_posts_is_on_the_page(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    result = run("plan", "estate")
    assert "AL-2" in result.output
    assert "no posts" in result.output
    assert "1 with no posts on them at all" in result.output


def test_a_read_line_reports_its_rate(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "600+00.00")
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
    result = run("plan", "estate")
    assert "100%" in result.output
    assert "1 of 1 judged posts" in result.output


def test_a_line_under_criterion_says_so(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "600+00.00")
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-780")
    assert "under criterion" in run("plan", "estate").output


def test_a_line_nobody_has_read_says_never_read(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "600+00.00")
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    assert "never read" in run("plan", "estate").output


def test_the_unbuilt_lines_sort_above_the_built_ones(
    run: Callable[..., Result],
) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "600+00.00")
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
    add_line(run, "ZZ-9", "Nothing yet", "1000 m")
    result = run("plan", "estate")
    assert result.output.index("ZZ-9") < result.output.index("AL-2")


def test_the_estate_length_is_added_up(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    add_line(run, "BR-9", "Brackenhill", "1500 m")
    assert "20.0 km" in run("plan", "estate").output


def test_open_findings_are_counted_per_line(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--summary",
        "under criterion",
    )
    result = run("plan", "estate")
    assert "Open" in result.output
    assert "AL-2" in result.output


def test_an_overdue_post_is_counted(run: Callable[..., Result]) -> None:
    add_line(run, "AL-2", "Ashfield lateral", "18500 m")
    add_segment(run, "AL-2-001", "AL-2", "600+00.00")
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905", "--date", "2022-05-02")
    result = run("plan", "estate")
    assert "Overdue" in result.output
