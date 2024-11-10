from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
        "post",
        "add",
        "TP-114",
        "--line",
        "AL-2",
        "--at",
        "12+45.50",
        "--installed",
        "1998-05-04",
    )
    run("post", "read", "TP-114", "--on", "-1120", "--off", "-905")
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "39+37.01",
        "--to",
        "41+00.00",
        "--summary",
        "under criterion",
    )


def test_findings_export_to_standard_output(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "export", "findings", "--line", "AL-2")
    assert result.exit_code == 0
    assert result.output.startswith("code,line_code")
    assert "F-2025-001" in result.output


def test_readings_export_to_standard_output(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "export", "readings", "--line", "AL-2")
    assert "test_point_code,lead" in result.output
    assert "-1120.0" in result.output


def test_an_export_can_be_written_to_a_file(run: Callable[..., Result], tmp_path: Path) -> None:
    seed(run)
    target = tmp_path / "findings.csv"
    result = run("report", "export", "findings", "--line", "AL-2", "--out", str(target))
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").startswith("code,line_code")


def test_a_closed_finding_is_left_out_unless_asked_for(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("finding", "clear", "F-2025-001", "--by", "J Sowerby")
    without = run("report", "export", "findings", "--line", "AL-2")
    assert "F-2025-001" not in without.output
    with_closed = run("report", "export", "findings", "--line", "AL-2", "--all")
    assert "F-2025-001" in with_closed.output


def test_readings_can_be_narrowed_to_a_lead(run: Callable[..., Result]) -> None:
    seed(run)
    only_casing = run("report", "export", "readings", "--line", "AL-2", "--lead", "casing")
    assert "TP-114" not in only_casing.output


def test_exporting_from_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("report", "export", "findings", "--line", "ZZ-9").exit_code == 3


def test_the_export_uses_the_line_stationing_convention(
    run: Callable[..., Result],
) -> None:
    seed(run)
    result = run("report", "export", "findings", "--line", "AL-2")
    assert "39+37.01" in result.output
