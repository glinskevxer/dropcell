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

ADD_UNIT = (
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


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_BED)
    run(*ADD_UNIT)


def add_check(
    run: Callable[..., Result],
    date: str,
    amps: str = "12.4",
    volts: str = "18.5",
    coarse: str = "3",
    fine: str = "2",
) -> None:
    run(
        "rectifier",
        "check",
        "RU-3",
        "--volts",
        volts,
        "--amps",
        amps,
        "--coarse",
        coarse,
        "--fine",
        fine,
        "--date",
        date,
    )


def test_a_line_with_no_units_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "no rectifiers on this line" in run("rectifier", "faults", "--line", "AL-2").output


def test_a_steady_unit_is_left_off_the_list(run: Callable[..., Result]) -> None:
    seed(run)
    for month in (1, 3, 5, 7):
        add_check(run, f"2024-{month:02d}-06")
    result = run("rectifier", "faults", "--line", "AL-2")
    assert "RU-3" not in result.output.split("units need somebody")[0].split("\n\n")[0]
    assert "0 of 1 units need somebody soon" in result.output


def test_a_steady_unit_can_be_shown_anyway(run: Callable[..., Result]) -> None:
    seed(run)
    for month in (1, 3, 5, 7):
        add_check(run, f"2024-{month:02d}-06")
    result = run("rectifier", "faults", "--line", "AL-2", "--all")
    assert "RU-3" in result.output
    assert "nothing found" in result.output


def test_a_dead_unit_is_reported_and_counted_urgent(run: Callable[..., Result]) -> None:
    seed(run)
    add_check(run, "2024-01-06")
    add_check(run, "2024-03-06")
    add_check(run, "2024-05-06", amps="0 A")
    result = run("rectifier", "faults", "--line", "AL-2")
    assert "dead" in result.output
    assert "1 of 1 units need somebody soon" in result.output


def test_a_falling_output_is_reported(run: Callable[..., Result]) -> None:
    seed(run)
    add_check(run, "2024-01-06", amps="12 A")
    add_check(run, "2024-03-06", amps="9 A")
    add_check(run, "2024-05-06", amps="6 A")
    result = run("rectifier", "faults", "--line", "AL-2")
    assert "output_falling" in result.output
    assert "output down" in result.output


def test_the_window_decides_how_far_back_it_reads(run: Callable[..., Result]) -> None:
    seed(run)
    add_check(run, "2020-01-06", amps="20 A")
    add_check(run, "2022-01-06", amps="12 A")
    add_check(run, "2024-01-06", amps="12 A")
    wide = run("rectifier", "faults", "--line", "AL-2", "--window", "6")
    assert "output_falling" in wide.output
    narrow = run("rectifier", "faults", "--line", "AL-2", "--window", "2")
    assert "output_falling" not in narrow.output


def test_a_line_with_no_beds_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "no groundbeds on this line" in run("rectifier", "beds", "--line", "AL-2").output


def test_a_bed_reports_what_it_has_passed(run: Callable[..., Result]) -> None:
    seed(run)
    add_check(run, "2015-01-06", amps="10 A")
    add_check(run, "2025-01-06", amps="10 A")
    result = run("rectifier", "beds", "--line", "AL-2")
    assert "GB-3" in result.output
    assert "high_silicon_iron" in result.output
    assert "Amp years" in result.output


def test_a_bed_on_a_dead_unit_has_no_projected_end(run: Callable[..., Result]) -> None:
    seed(run)
    add_check(run, "2024-01-06", amps="10 A")
    add_check(run, "2025-01-06", amps="0 A")
    result = run("rectifier", "beds", "--line", "AL-2")
    assert "unit is off" in result.output


def test_the_horizon_counts_the_beds_that_run_out_in_it(
    run: Callable[..., Result],
) -> None:
    seed(run)
    add_check(run, "1998-01-06", amps="15 A")
    add_check(run, "2025-01-06", amps="15 A")
    near = run("rectifier", "beds", "--line", "AL-2", "--horizon", "1")
    assert "1 of 1 beds run out inside 1 years" in near.output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("rectifier", "faults", "--line", "ZZ-9").exit_code == 3
    assert run("rectifier", "beds", "--line", "ZZ-9").exit_code == 3
