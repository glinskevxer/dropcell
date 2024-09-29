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


def test_a_line_can_be_added_and_listed(run: Callable[..., Result]) -> None:
    added = run(*ADD_LINE)
    assert added.exit_code == 0
    assert "AL-2 added" in added.output
    listed = run("line", "list")
    assert "AL-2" in listed.output
    assert "Ashfield lateral" in listed.output


def test_an_empty_register_lists_nothing(run: Callable[..., Result]) -> None:
    assert "no lines in the register" in run("line", "list").output


def test_a_length_in_miles_lands_on_the_same_number(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "line",
        "add",
        "BR-9",
        "--name",
        "Brackenhill",
        "--operator",
        "N",
        "--length",
        "10 mi",
        "--diameter",
        "610 mm",
        "--installed",
        "1991",
    )
    listed = run("line", "list")
    assert "16093" in listed.output


def test_the_same_code_twice_is_a_conflict(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    again = run(*ADD_LINE)
    assert again.exit_code == 4
    assert "conflict:" in again.output


def test_an_impossible_install_year_is_a_usage_error(run: Callable[..., Result]) -> None:
    result = run(
        "line",
        "add",
        "X-1",
        "--name",
        "x",
        "--operator",
        "y",
        "--length",
        "100 m",
        "--diameter",
        "100 mm",
        "--installed",
        "1700",
    )
    assert result.exit_code == 2
    assert "validation:" in result.output


def test_showing_a_line_prints_its_details(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    shown = run("line", "show", "AL-2")
    assert "Ashfield lateral" in shown.output
    assert "Northmoor Gas" in shown.output
    assert "no segments on this line" in shown.output


def test_showing_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    result = run("line", "show", "ZZ-9")
    assert result.exit_code == 3
    assert "not_found:" in result.output


def test_a_segment_can_be_added_and_listed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    added = run(*ADD_SEGMENT)
    assert added.exit_code == 0
    assert "AL-2-004 added" in added.output
    listed = run("segment", "list", "--line", "AL-2")
    assert "coal_tar" in listed.output
    assert "0+00.00" in listed.output


def test_a_segment_shows_up_under_its_line(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    shown = run("line", "show", "AL-2")
    assert "AL-2-004" in shown.output


def test_two_segments_on_the_same_pipe_are_refused(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    clash = run(*ADD_SEGMENT[:2], "AL-2-005", *ADD_SEGMENT[3:])
    assert clash.exit_code == 4


def test_an_overlap_can_be_forced(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    forced = run(*ADD_SEGMENT[:2], "AL-2-005", *ADD_SEGMENT[3:], "--allow-overlap")
    assert forced.exit_code == 0


def test_a_soil_resistivity_can_be_given_in_ohm_centimetres(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT, "--soil", "4500 ohm-cm")
    listed = run("segment", "list", "--line", "AL-2")
    assert "45.0" in listed.output


def test_a_segment_on_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run(*ADD_SEGMENT).exit_code == 3


def test_removing_a_line_asks_first(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    refused = run("line", "remove", "AL-2", input_text="n\n")
    assert refused.exit_code != 0
    assert "AL-2" in run("line", "list").output


def test_removing_a_line_takes_its_segments(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    removed = run("line", "remove", "AL-2", input_text="y\n")
    assert removed.exit_code == 0
    assert "no lines in the register" in run("line", "list").output
