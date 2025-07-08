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
        "rectifier",
        "add-bed",
        "GB-1",
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


def add_unit(run: Callable[..., Result], tag: str, station: str, rated: str = "20") -> None:
    run(
        "rectifier",
        "add",
        tag,
        "--line",
        "AL-2",
        "--at",
        station,
        "--bed",
        "GB-1",
        "--rated-volts",
        "24",
        "--rated-amps",
        rated,
        "--installed",
        "2004-09-01",
    )


def check(run: Callable[..., Result], tag: str, amps: str) -> None:
    run(
        "rectifier",
        "check",
        tag,
        "--volts",
        "18.5",
        "--amps",
        amps,
        "--coarse",
        "3",
        "--fine",
        "2",
    )


def test_a_line_with_no_units_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run("plan", "balance", "--line", "AL-2")
    assert result.exit_code == 0
    assert "no rectifiers on this line" in result.output


def test_an_even_line_is_not_called_concentrated(run: Callable[..., Result]) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00")
    add_unit(run, "RU-2", "300+00.00")
    check(run, "RU-1", "5 A")
    check(run, "RU-2", "5 A")
    result = run("plan", "balance", "--line", "AL-2")
    assert "2 of 2 units working" in result.output
    assert "largest carrying 50%" in result.output
    assert "carrying most of this line" not in result.output


def test_one_unit_carrying_the_line_is_named(run: Callable[..., Result]) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00")
    add_unit(run, "RU-2", "300+00.00")
    check(run, "RU-1", "9 A")
    check(run, "RU-2", "1 A")
    result = run("plan", "balance", "--line", "AL-2")
    assert "one unit is carrying most of this line" in result.output


def test_a_unit_nobody_has_read_is_shown_dead(run: Callable[..., Result]) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00")
    add_unit(run, "RU-2", "300+00.00")
    check(run, "RU-1", "9 A")
    result = run("plan", "balance", "--line", "AL-2")
    assert "1 of 2 units working" in result.output
    assert "dead" in result.output


def test_a_unit_at_its_nameplate_is_shown_at_capacity(
    run: Callable[..., Result],
) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00")
    check(run, "RU-1", "19 A")
    assert "at capacity" in run("plan", "balance", "--line", "AL-2").output


def test_the_widest_gap_is_reported(run: Callable[..., Result]) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00")
    add_unit(run, "RU-2", "300+00.00")
    check(run, "RU-1", "5 A")
    check(run, "RU-2", "5 A")
    result = run("plan", "balance", "--line", "AL-2")
    assert "the widest gap between neighbouring units" in result.output


def test_a_single_unit_line_reports_no_gap(run: Callable[..., Result]) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00")
    check(run, "RU-1", "5 A")
    result = run("plan", "balance", "--line", "AL-2")
    assert "widest gap" not in result.output


def test_a_line_that_could_lose_its_biggest_unit_says_so(
    run: Callable[..., Result],
) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00")
    add_unit(run, "RU-2", "300+00.00")
    check(run, "RU-1", "5 A")
    check(run, "RU-2", "5 A")
    assert (
        "enough rating to lose the largest unit"
        in run("plan", "balance", "--line", "AL-2").output
    )


def test_a_line_that_could_not_says_so(run: Callable[..., Result]) -> None:
    seed(run)
    add_unit(run, "RU-1", "10+00.00", rated="20")
    add_unit(run, "RU-2", "300+00.00", rated="5")
    check(run, "RU-1", "18 A")
    check(run, "RU-2", "4 A")
    assert "not enough spare rating" in run("plan", "balance", "--line", "AL-2").output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("plan", "balance", "--line", "ZZ-9").exit_code == 3
