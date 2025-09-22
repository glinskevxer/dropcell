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

LAYERED = (
    HEADER
    + "6+00.00,2025-03-14,1 m,31.831,\n"
    + "6+00.00,2025-03-14,2 m,2.2208,\n"
    + "6+00.00,2025-03-14,3 m,1.8018,\n"
)
"""Benign in the top metre, corrosive in the second, mild in the third."""


def add_segment(
    run: Callable[..., Result],
    code: str,
    *,
    start: str,
    end: str,
    cover: str = "1.2 m",
    soil: str | None = None,
) -> Result:
    argv = [
        "segment",
        "add",
        code,
        "--line",
        "AL-2",
        "--coating",
        "coal_tar",
        "--from",
        start,
        "--to",
        end,
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1974",
        "--cover",
        cover,
    ]
    if soil is not None:
        argv += ["--soil", soil]
    result = run(*argv)
    assert result.exit_code == 0, result.output
    return result


@pytest.fixture
def soil_file(tmp_path: Path) -> Callable[[str], Path]:
    def write(text: str) -> Path:
        target = tmp_path / "soil.csv"
        target.write_text(text, encoding="utf-8")
        return target

    return write


@pytest.fixture
def loaded(
    run: Callable[..., Result], soil_file: Callable[[str], Path]
) -> Callable[..., Result]:
    """A line with one layered sounding on it, ready for segments."""
    run(*ADD_LINE)
    run("survey", "soil", str(soil_file(LAYERED)), "--line", "AL-2")
    return run


def test_a_segment_filed_benign_over_a_corrosive_layer_is_called_out(
    loaded: Callable[..., Result],
) -> None:
    add_segment(loaded, "AL-2-001", start="0+00.00", end="12+00.00", soil="200 ohm-m")
    result = loaded("survey", "ground", "--line", "AL-2")

    assert result.exit_code == 0
    assert "AL-2-001" in result.output
    assert "understated" in result.output
    assert "1 filed kinder than the ground reads" in result.output


def test_the_depth_of_cover_decides_which_layer_is_read(
    loaded: Callable[..., Result],
) -> None:
    add_segment(
        loaded, "AL-2-001", start="0+00.00", end="5+00.00", cover="0.5 m", soil="200 ohm-m"
    )
    add_segment(
        loaded, "AL-2-002", start="7+00.00", end="12+00.00", cover="1.5 m", soil="200 ohm-m"
    )
    result = loaded("survey", "ground", "--line", "AL-2")

    assert result.exit_code == 0
    shallow = next(row for row in result.output.splitlines() if "AL-2-001" in row)
    deep = next(row for row in result.output.splitlines() if "AL-2-002" in row)
    assert "agrees" in shallow
    assert "understated" in deep


def test_a_segment_with_no_filed_figure_is_counted_separately(
    loaded: Callable[..., Result],
) -> None:
    add_segment(loaded, "AL-2-001", start="0+00.00", end="12+00.00")
    result = loaded("survey", "ground", "--line", "AL-2")

    assert result.exit_code == 0
    assert "not filed" in result.output
    assert "1 carry no filed resistivity at all" in result.output


def test_the_flag_narrows_the_table_to_the_ones_worth_acting_on(
    loaded: Callable[..., Result],
) -> None:
    add_segment(loaded, "AL-2-001", start="0+00.00", end="5+00.00", soil="200 ohm-m")
    add_segment(loaded, "AL-2-002", start="7+00.00", end="12+00.00", soil="15 ohm-m")
    result = loaded("survey", "ground", "--line", "AL-2", "--only-understated")

    assert result.exit_code == 0
    assert "AL-2-001" in result.output
    assert "AL-2-002" not in result.output


def test_a_line_with_no_soundings_says_so_rather_than_printing_an_empty_table(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    add_segment(run, "AL-2-001", start="0+00.00", end="12+00.00", soil="200 ohm-m")
    result = run("survey", "ground", "--line", "AL-2")

    assert result.exit_code == 0
    assert "nothing to compare against" in result.output


def test_an_unknown_line_is_refused(run: Callable[..., Result]) -> None:
    result = run("survey", "ground", "--line", "NOPE")
    assert result.exit_code != 0
