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


def test_a_segment_can_be_split(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("segment", "split", "AL-2-001", "--at", "300+00.00")
    assert result.exit_code == 0
    assert "split at 300+00.00 into AL-2-001-A and AL-2-001-B" in result.output
    listed = run("segment", "list", "--line", "AL-2")
    assert "AL-2-001-A" in listed.output
    assert "AL-2-001-B" in listed.output


def test_the_halves_report_their_lengths(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("segment", "split", "AL-2-001", "--at", "300+00.00")
    assert "9144 m" in result.output


def test_the_command_says_the_halves_inherit_everything(
    run: Callable[..., Result],
) -> None:
    seed(run)
    result = run("segment", "split", "AL-2-001", "--at", "300+00.00")
    assert "both halves carry what the original did" in result.output


def test_the_codes_can_be_given(run: Callable[..., Result]) -> None:
    seed(run)
    result = run(
        "segment",
        "split",
        "AL-2-001",
        "--at",
        "300+00.00",
        "--left",
        "AL-2-001",
        "--right",
        "AL-2-002",
    )
    assert "AL-2-001 and AL-2-002" in result.output


def test_splitting_off_the_line_is_a_usage_error(run: Callable[..., Result]) -> None:
    seed(run)
    assert run("segment", "split", "AL-2-001", "--at", "9999+00.00").exit_code == 2


def test_splitting_off_the_segment_is_a_usage_error(
    run: Callable[..., Result],
) -> None:
    seed(run)
    result = run("segment", "split", "AL-2-001", "--at", "590+00.00")
    assert result.exit_code == 0
    assert run("segment", "split", "AL-2-001-B", "--at", "10+00.00").exit_code == 2


def test_splitting_at_an_end_is_a_usage_error(run: Callable[..., Result]) -> None:
    seed(run)
    assert run("segment", "split", "AL-2-001", "--at", "0+00.00").exit_code == 2


def test_splitting_a_segment_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    seed(run)
    assert run("segment", "split", "AL-2-009", "--at", "300+00.00").exit_code == 3


def test_a_post_on_the_line_still_lands_on_a_segment(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run(
        "post",
        "add",
        "TP-1",
        "--line",
        "AL-2",
        "--at",
        "400+00.00",
        "--installed",
        "1998-05-04",
    )
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
    run("segment", "split", "AL-2-001", "--at", "300+00.00")
    report = run("report", "protection", "--line", "AL-2")
    assert "AL-2-001-B" in report.output
    assert "1 posts, 1 judged" in report.output
