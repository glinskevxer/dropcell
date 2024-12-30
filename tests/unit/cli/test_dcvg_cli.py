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
    "--soil",
    "800 ohm-cm",
)

HEADER = "Station,Date,Gradient,Total Shift,Anodic,Remark\n"
GOOD = (
    HEADER
    + "12+45.50,2025-03-14,40,400,,\n"
    + "180+00.00,2025-03-14,300,400,,at the road bore\n"
    + "220+10.00,2025-03-14,60,400,y,\n"
)


@pytest.fixture
def dcvg_file(tmp_path: Path) -> Callable[[str], Path]:
    counter = {"n": 0}

    def write(text: str) -> Path:
        counter["n"] += 1
        target = tmp_path / f"dcvg-{counter['n']}.csv"
        target.write_text(text, encoding="utf-8")
        return target

    return write


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)


def test_a_gradient_file_becomes_a_dig_sheet(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    result = run("survey", "dcvg", str(dcvg_file(GOOD)), "--line", "AL-2")
    assert result.exit_code == 0
    assert "3 indications read" in result.output
    assert "Dig sheet, AL-2" in result.output
    assert "AL-2-D001" in result.output


def test_the_sheet_is_ordered_worst_first(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    result = run("survey", "dcvg", str(dcvg_file(GOOD)), "--line", "AL-2")
    table = result.output.split("Excavations")[1]
    assert table.index("AL-2-D001") < table.index("AL-2-D003")


def test_the_scoring_is_written_out_under_the_sheet(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    result = run("survey", "dcvg", str(dcvg_file(GOOD)), "--line", "AL-2")
    assert "How each score was reached" in result.output
    assert " x " in result.output
    assert "soil very_corrosive" in result.output


def test_a_budget_trims_the_sheet(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    result = run("survey", "dcvg", str(dcvg_file(GOOD)), "--line", "AL-2", "--budget", "1")
    sheet = result.output.split("Excavations")[1]
    assert "AL-2-D001" in sheet
    assert "AL-2-D002" not in sheet
    assert "AL-2-D003" not in sheet


def test_a_contact_appears_on_the_sheet(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    result = run(
        "survey",
        "dcvg",
        str(dcvg_file(GOOD)),
        "--line",
        "AL-2",
        "--contact",
        "control room 0800 111 999",
    )
    assert "call control room 0800 111 999" in result.output


def test_an_indication_off_every_segment_is_reported_not_scored(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    text = GOOD + "900+00.00,2025-03-14,40,400,,\n"
    result = run("survey", "dcvg", str(dcvg_file(text)), "--line", "AL-2")
    assert "1 indications sit on pipe no segment describes" in result.output


def test_a_file_with_no_dates_can_take_one_on_the_command_line(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    text = "Station,Gradient,Total Shift\n12+45.50,40,400\n18+00.00,300,400\n"
    result = run(
        "survey", "dcvg", str(dcvg_file(text)), "--line", "AL-2", "--date", "2025-03-14"
    )
    assert "2 indications read" in result.output


def test_the_same_file_twice_is_a_conflict(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    seed(run)
    target = dcvg_file(GOOD)
    run("survey", "dcvg", str(target), "--line", "AL-2")
    assert run("survey", "dcvg", str(target), "--line", "AL-2").exit_code == 4


def test_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result], dcvg_file: Callable[[str], Path]
) -> None:
    assert run("survey", "dcvg", str(dcvg_file(GOOD)), "--line", "ZZ-9").exit_code == 3
