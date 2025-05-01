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
        "segment",
        "add",
        "AL-2-001",
        "--line",
        "AL-2",
        "--from",
        "0+00.00",
        "--to",
        "100+00.00",
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
        "segment",
        "add",
        "AL-2-002",
        "--line",
        "AL-2",
        "--from",
        "100+00.01",
        "--to",
        "300+00.00",
        "--coating",
        "tape_wrap",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1982",
        "--class-location",
        "4",
        "--protection",
        "unprotected",
    )


def test_a_line_with_no_segments_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "no segments on this line" in run("report", "risk", "--line", "AL-2").output


def test_every_segment_gets_a_score(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "risk", "--line", "AL-2")
    assert result.exit_code == 0
    assert "AL-2-001" in result.output
    assert "AL-2-002" in result.output
    assert "2 segments" in result.output


def test_the_unprotected_shielded_urban_segment_scores_highest(
    run: Callable[..., Result],
) -> None:
    seed(run)
    table = run("report", "risk", "--line", "AL-2").output.split("Segment risk")[1]
    assert table.index("AL-2-002") < table.index("AL-2-001")


def test_the_ordering_can_be_weighted_by_length(run: Callable[..., Result]) -> None:
    seed(run)
    plain = run("report", "risk", "--line", "AL-2").output
    weighted = run("report", "risk", "--line", "AL-2", "--by-length").output
    assert "Score km" in plain
    assert "Score km" in weighted


def test_the_scoring_can_be_written_out(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "risk", "--line", "AL-2", "--explain")
    assert " x " in result.output
    assert "no protection on it" in result.output


def test_a_post_raises_the_covered_share(run: Callable[..., Result]) -> None:
    seed(run)
    without = run("report", "risk", "--line", "AL-2").output
    run(
        "post", "add", "TP-1", "--line", "AL-2", "--at", "50+00.00", "--installed", "1998-05-04"
    )
    withpost = run("report", "risk", "--line", "AL-2").output
    assert "0%" in without
    assert withpost != without


def test_a_fully_covered_segment_carries_no_reach_term(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(
        "segment",
        "add",
        "AL-2-001",
        "--line",
        "AL-2",
        "--from",
        "0+00.00",
        "--to",
        "10+00.00",
        "--coating",
        "coal_tar",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1974",
    )
    run("post", "add", "TP-1", "--line", "AL-2", "--at", "5+00.00", "--installed", "1998-05-04")
    result = run("report", "risk", "--line", "AL-2", "--explain")
    assert "out of reach" not in result.output
    assert "100%" in result.output


def test_the_total_exposure_is_printed(run: Callable[..., Result]) -> None:
    seed(run)
    assert "total exposure" in run("report", "risk", "--line", "AL-2").output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("report", "risk", "--line", "ZZ-9").exit_code == 3
