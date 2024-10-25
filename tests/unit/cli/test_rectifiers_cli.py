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


def test_a_bed_reports_its_mass_and_design_life(run: Callable[..., Result]) -> None:
    added = run(*ADD_BED)
    assert added.exit_code == 0
    assert "200 kg" in added.output
    assert "design life 25 years" in added.output


def test_a_bed_mass_can_be_given_in_pounds(run: Callable[..., Result]) -> None:
    added = run(
        "rectifier",
        "add-bed",
        "GB-9",
        "--kind",
        "deep_well",
        "--material",
        "graphite",
        "--anodes",
        "10",
        "--mass",
        "44 lb",
        "--installed",
        "2004-09-01",
        "--design-current",
        "15 A",
    )
    assert "200 kg" in added.output


def test_a_mass_that_cannot_be_read_is_a_usage_error(run: Callable[..., Result]) -> None:
    result = run(
        "rectifier",
        "add-bed",
        "GB-9",
        "--kind",
        "deep_well",
        "--material",
        "graphite",
        "--anodes",
        "10",
        "--mass",
        "heavy",
        "--installed",
        "2004-09-01",
        "--design-current",
        "15 A",
    )
    assert result.exit_code == 2
    assert "unit:" in result.output


def test_a_galvanic_string_of_graphite_is_refused(run: Callable[..., Result]) -> None:
    result = run(
        "rectifier",
        "add-bed",
        "GB-9",
        "--kind",
        "galvanic_string",
        "--material",
        "graphite",
        "--anodes",
        "10",
        "--mass",
        "20 kg",
        "--installed",
        "2004-09-01",
        "--design-current",
        "1 A",
    )
    assert result.exit_code == 2


def test_a_unit_can_be_added_and_shows_in_status(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_BED)
    added = run(*ADD_UNIT)
    assert added.exit_code == 0
    assert "RU-3 added at 138+00.00" in added.output
    status = run("rectifier", "status", "--line", "AL-2")
    assert "RU-3" in status.output
    assert "never" in status.output


def test_a_unit_on_a_bed_that_is_not_there_is_a_conflict(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    assert run(*ADD_UNIT).exit_code == 4


def test_a_check_can_be_recorded_and_shows_in_status(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_BED)
    run(*ADD_UNIT)
    checked = run(
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
    assert checked.exit_code == 0
    status = run("rectifier", "status", "--line", "AL-2")
    assert "18.5" in status.output
    assert "12.40" in status.output
    assert "62%" in status.output


def test_a_tap_off_the_board_is_a_usage_error(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_BED)
    run(*ADD_UNIT)
    result = run(
        "rectifier",
        "check",
        "RU-3",
        "--volts",
        "18.5",
        "--amps",
        "12.4",
        "--coarse",
        "9",
        "--fine",
        "2",
    )
    assert result.exit_code == 2
    assert "board" in result.output


def test_a_second_check_on_the_same_day_is_a_conflict(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_BED)
    run(*ADD_UNIT)
    args = (
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
    run(*args)
    assert run(*args).exit_code == 4


def test_the_status_shows_the_circuit_resistance(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_BED)
    run(*ADD_UNIT)
    run(
        "rectifier",
        "check",
        "RU-3",
        "--volts",
        "20",
        "--amps",
        "10",
        "--coarse",
        "3",
        "--fine",
        "2",
    )
    assert "2.00" in run("rectifier", "status", "--line", "AL-2").output


def test_the_status_shows_how_spent_the_bed_is(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_BED)
    run(*ADD_UNIT)
    run(
        "rectifier",
        "check",
        "RU-3",
        "--volts",
        "20",
        "--amps",
        "10",
        "--coarse",
        "3",
        "--fine",
        "2",
        "--date",
        "2010-01-01",
    )
    status = run("rectifier", "status", "--line", "AL-2")
    assert "%" in status.output


def test_a_line_with_no_units_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "no rectifiers on this line" in run("rectifier", "status", "--line", "AL-2").output


def test_checking_a_unit_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    result = run(
        "rectifier",
        "check",
        "RU-9",
        "--volts",
        "18",
        "--amps",
        "1",
        "--coarse",
        "1",
        "--fine",
        "1",
    )
    assert result.exit_code == 3
