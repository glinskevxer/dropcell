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

ADD_BED = (
    "rectifier",
    "add-bed",
    "GB-3",
    "--kind",
    "deep_well",
    "--material",
    "high_silicon_iron",
    "--anodes",
    "10",
    "--mass",
    "20 kg",
    "--installed",
    "2004-09-01",
    "--design-current",
    "15 A",
)


def add_segment(
    run: Callable[..., Result], code: str, start: str, end: str, coating: str = "coal_tar"
) -> None:
    run(
        "segment",
        "add",
        code,
        "--line",
        "AL-2",
        "--from",
        start,
        "--to",
        end,
        "--coating",
        coating,
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1974",
    )


def test_a_line_with_no_segments_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run("plan", "coating", "--line", "AL-2")
    assert result.exit_code == 0
    assert "nothing to compare against" in result.output


def test_a_line_with_no_current_anywhere_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "600+00.00")
    result = run("plan", "coating", "--line", "AL-2")
    assert "no rectifier has been read" in result.output


def test_a_current_can_be_given_on_the_command_line(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "600+00.00")
    result = run("plan", "coating", "--line", "AL-2", "--current", "2 A")
    assert "2.00 A on the line" in result.output
    assert "AL-2-001" in result.output


def test_the_verdict_follows_the_factor(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "600+00.00")
    quiet = run("plan", "coating", "--line", "AL-2", "--current", "0.01 A")
    assert "as laid" in quiet.output
    loud = run("plan", "coating", "--line", "AL-2", "--current", "400 A")
    assert "failed" in loud.output or "degraded" in loud.output


def test_a_single_segment_is_not_called_a_guess(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "600+00.00")
    result = run("plan", "coating", "--line", "AL-2", "--current", "2 A")
    assert "which is a guess" not in result.output


def test_several_segments_are(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "300+00.00")
    add_segment(run, "AL-2-002", "300+00.01", "600+00.00", coating="bare")
    result = run("plan", "coating", "--line", "AL-2", "--current", "2 A")
    assert "which is a guess" in result.output


def test_the_bare_segment_takes_most_of_the_current(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "300+00.00")
    add_segment(run, "AL-2-002", "300+00.01", "600+00.00", coating="bare")
    table = run("plan", "coating", "--line", "AL-2", "--current", "2 A").output
    assert table.index("AL-2-00") >= 0


def test_the_comparison_can_be_written_out(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "600+00.00")
    result = run("plan", "coating", "--line", "AL-2", "--current", "2 A", "--explain")
    assert "drawing" in result.output
    assert "as laid" in result.output


def test_the_rectifier_checks_are_used_when_no_current_is_given(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "600+00.00")
    run(*ADD_BED)
    run(
        "rectifier",
        "add",
        "RU-3",
        "--line",
        "AL-2",
        "--at",
        "138+00.00",
        "--bed",
        "GB-3",
        "--rated-volts",
        "24",
        "--rated-amps",
        "20",
        "--installed",
        "2004-09-01",
    )
    run(
        "rectifier",
        "check",
        "RU-3",
        "--volts",
        "18.5",
        "--amps",
        "12.4",
        "--coarse",
        "3",
        "--fine",
        "2",
    )
    result = run("plan", "coating", "--line", "AL-2")
    assert "12.40 A on the line" in result.output
    assert "the last check on 1 rectifiers" in result.output


def test_the_count_worth_surveying_is_printed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", "0+00.00", "600+00.00")
    result = run("plan", "coating", "--line", "AL-2", "--current", "200 A")
    assert "1 of 1 segments are worth a gradient survey" in result.output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("plan", "coating", "--line", "ZZ-9").exit_code == 3
