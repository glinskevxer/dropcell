from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
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

HEADER = "Station,Date,Pin Spacing,Resistance,Remark\n"
GOOD = (
    HEADER
    + "12+45.50,2025-03-14,1 m,20,\n"
    + "12+45.50,2025-03-14,2 m,8,\n"
    + "12+45.50,2025-03-14,3 m,5,\n"
    + "40+00.00,2025-03-14,1 m,40,\n"
    + "40+00.00,2025-03-14,2 m,18,\n"
)


@pytest.fixture
def soil_file(tmp_path: Path) -> Callable[[str], Path]:
    counter = {"n": 0}

    def write(text: str) -> Path:
        counter["n"] += 1
        target = tmp_path / f"soil-{counter['n']}.csv"
        target.write_text(text, encoding="utf-8")
        return target

    return write


def test_a_file_becomes_soundings(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    result = run("survey", "soil", str(soil_file(GOOD)), "--line", "AL-2")
    assert result.exit_code == 0
    assert "2 soundings stored" in result.output
    assert "12+45.50" in result.output
    assert "40+00.00" in result.output


def test_the_table_reports_the_ground_at_the_depth_asked_for(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    shallow = run("survey", "soil", str(soil_file(GOOD)), "--line", "AL-2", "--depth", "0.5 m")
    assert "At cover" in shallow.output
    assert "Band" in shallow.output


def test_a_group_with_one_spacing_is_reported_not_stored(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = GOOD + "80+00.00,2025-03-14,1 m,40,\n"
    result = run("survey", "soil", str(soil_file(text)), "--line", "AL-2")
    assert "2 soundings stored" in result.output
    assert "at least two spacings" in result.output


def test_two_days_at_one_place_are_two_soundings(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = (
        HEADER
        + "12+45.50,2025-03-14,1 m,20,\n"
        + "12+45.50,2025-03-14,2 m,8,\n"
        + "12+45.50,2024-03-14,1 m,22,\n"
        + "12+45.50,2024-03-14,2 m,9,\n"
    )
    result = run("survey", "soil", str(soil_file(text)), "--line", "AL-2")
    assert "2 soundings stored" in result.output


def test_a_broken_row_is_quarantined_and_counted(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = GOOD + "12+45.50,not a date,4 m,3,\n"
    result = run("survey", "soil", str(soil_file(text)), "--line", "AL-2")
    assert "1 rows could not be read" in result.output


def test_the_same_file_twice_is_a_conflict(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    target = soil_file(GOOD)
    run("survey", "soil", str(target), "--line", "AL-2")
    assert run("survey", "soil", str(target), "--line", "AL-2").exit_code == 4


def test_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    assert run("survey", "soil", str(soil_file(GOOD)), "--line", "ZZ-9").exit_code == 3


def test_spacings_in_feet_land_in_metres(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = HEADER + "12+45.50,2025-03-14,5 ft,20,\n" + "12+45.50,2025-03-14,10 ft,8,\n"
    result = run("survey", "soil", str(soil_file(text)), "--line", "AL-2")
    assert "1 soundings stored" in result.output
