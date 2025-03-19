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
        "plant",
        "add-casing",
        "CS-12",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--length",
        "32 m",
        "--carries",
        "the A19",
        "--installed",
        "1998-05-04",
    )
    run(
        "plant",
        "add-crossing",
        "XG-4",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--operator",
        "Vale Water",
        "--structure",
        "18 inch main",
    )
    run(
        "plant",
        "add-bond",
        "BD-7",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--kind",
        "direct",
        "--to",
        "Vale Water main",
        "--design-current",
        "2 A",
        "--installed",
        "2011-04-02",
        "--critical",
    )
    run(
        "plant",
        "add-joint",
        "IJ-2",
        "--line",
        "AL-2",
        "--at",
        "1+00.00",
        "--kind",
        "monolithic",
        "--separates",
        "compressor station",
        "--installed",
        "2004-09-01",
    )


def test_an_empty_line_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run("report", "interference", "--line", "AL-2")
    assert result.exit_code == 0
    assert "nothing on this line but pipe, posts and rectifiers" in result.output


def test_everything_untested_shows_up(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "interference", "--line", "AL-2")
    for code in ("CS-12", "XG-4", "BD-7", "IJ-2"):
        assert code in result.output
    assert "4 pieces of plant, 4 never tested" in result.output


def test_a_tested_piece_carries_its_verdict(run: Callable[..., Result]) -> None:
    seed(run)
    run("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-560")
    result = run("report", "interference", "--line", "AL-2")
    assert "clear" in result.output
    assert "3 never tested" in result.output


def test_a_shorted_casing_is_counted_as_needing_work(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-1116")
    result = run("report", "interference", "--line", "AL-2")
    assert "metallic_short" in result.output
    assert "3 never tested, 1 needing work" in result.output


def test_the_untested_sort_above_the_tested(run: Callable[..., Result]) -> None:
    seed(run)
    run("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-560")
    result = run("report", "interference", "--line", "AL-2")
    table = result.output.split("Interference")[1]
    assert table.index("IJ-2") < table.index("CS-12")


def test_an_open_critical_bond_says_protection_depends_on_it(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("plant", "test-bond", "BD-7", "--current", "0 A")
    result = run("report", "interference", "--line", "AL-2")
    assert "protection depends on this bond" in result.output


def test_the_latest_test_is_the_one_reported(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "plant",
        "test-casing",
        "CS-12",
        "--pipe-on",
        "-1120",
        "--casing-on",
        "-1116",
        "--date",
        "2024-03-14",
    )
    run(
        "plant",
        "test-casing",
        "CS-12",
        "--pipe-on",
        "-1120",
        "--casing-on",
        "-560",
        "--date",
        "2025-03-14",
    )
    result = run("report", "interference", "--line", "AL-2")
    assert "clear" in result.output
    assert "metallic_short" not in result.output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("report", "interference", "--line", "ZZ-9").exit_code == 3
