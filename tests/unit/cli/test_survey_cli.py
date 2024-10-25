from __future__ import annotations

from collections.abc import Callable, Sequence
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

HEADER = "Station,P/S On,P/S Off,Remark\n"


def walk(offs: Sequence[float | None], step_ft: float = 5.0) -> str:
    rows = []
    for index, off in enumerate(offs):
        feet = index * step_ft
        major, minor = divmod(feet, 100)
        text = "" if off is None else f"{off:.0f}"
        rows.append(f"{int(major)}+{minor:05.2f},-1120,{text},\n")
    return HEADER + "".join(rows)


@pytest.fixture
def cis_file(tmp_path: Path) -> Callable[[str], Path]:
    counter = {"n": 0}

    def write(text: str) -> Path:
        counter["n"] += 1
        target = tmp_path / f"cis-{counter['n']}.csv"
        target.write_text(text, encoding="utf-8")
        return target

    return write


def test_a_clean_walk_reports_no_sections(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    target = cis_file(walk([-905.0] * 12))
    result = run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert result.exit_code == 0
    assert "12 steps" in result.output
    assert "nothing under criterion" in result.output
    assert "0 sections" in result.output


def test_a_failing_stretch_is_cut_into_a_section(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    offs: Sequence[float | None] = [-905.0] * 4 + [-800.0] * 3 + [-905.0] * 4
    target = cis_file(walk(offs))
    result = run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert "1 sections" in result.output
    assert "moderate" in result.output or "severe" in result.output


def test_the_threshold_can_be_moved(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    target = cis_file(walk([-905.0] * 12))
    result = run(
        "survey",
        "cis",
        str(target),
        "--line",
        "AL-2",
        "--date",
        "2025-03-14",
        "--threshold",
        "-950 mV",
    )
    assert "1 sections" in result.output


def test_a_contact_spike_is_dropped_by_default(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = walk([-905.0] * 12).replace("0+25.00,-1120,-905,", "0+25.00,-620,-400,")
    target = cis_file(text)
    result = run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert "Suspected contact spikes, dropped" in result.output
    assert "0 sections" in result.output


def test_a_contact_spike_can_be_kept(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = walk([-905.0] * 12).replace("0+25.00,-1120,-905,", "0+25.00,-620,-400,")
    target = cis_file(text)
    result = run(
        "survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14", "--keep-spikes"
    )
    assert "kept" in result.output
    assert "1 sections" in result.output


def test_short_sections_can_be_filtered_out(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    offs: Sequence[float | None] = [-905.0] * 4 + [-800.0] + [-905.0] * 4
    target = cis_file(walk(offs))
    kept = run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert "1 sections" in kept.output
    target2 = cis_file(walk(offs) + "9+99.00,-1120,-905,\n")
    dropped = run(
        "survey",
        "cis",
        str(target2),
        "--line",
        "AL-2",
        "--date",
        "2025-03-14",
        "--minimum",
        "10 m",
    )
    assert "0 sections" in dropped.output


def test_findings_are_only_raised_when_asked_for(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    offs: Sequence[float | None] = [-905.0] * 4 + [-800.0] * 3 + [-905.0] * 4
    target = cis_file(walk(offs))
    run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert "no exceptions raised" in run("report", "exceptions").output


def test_findings_can_be_raised_from_the_survey(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    offs: Sequence[float | None] = [-905.0] * 4 + [-800.0] * 3 + [-905.0] * 4
    target = cis_file(walk(offs))
    result = run(
        "survey",
        "cis",
        str(target),
        "--line",
        "AL-2",
        "--date",
        "2025-03-14",
        "--raise-findings",
        "--by",
        "R Ellis",
    )
    assert "1 findings raised" in result.output
    assert "F-2025-001" in run("report", "exceptions").output


def test_a_stepped_over_stretch_is_reported(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = walk([-905.0] * 6) + "40+00.00,-1120,-905,\n41+00.00,-1120,-905,\n"
    target = cis_file(text)
    result = run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert "stepped over rather than walked" in result.output


def test_the_same_file_twice_is_a_conflict(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    target = cis_file(walk([-905.0] * 12))
    run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    again = run("survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14")
    assert again.exit_code == 4


def test_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    target = cis_file(walk([-905.0] * 12))
    result = run("survey", "cis", str(target), "--line", "ZZ-9", "--date", "2025-03-14")
    assert result.exit_code == 3


def test_the_walking_step_can_be_overridden(
    run: Callable[..., Result], cis_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    target = cis_file(walk([-905.0] * 12))
    result = run(
        "survey", "cis", str(target), "--line", "AL-2", "--date", "2025-03-14", "--step", "3 m"
    )
    assert "at 3.00 m" in result.output
