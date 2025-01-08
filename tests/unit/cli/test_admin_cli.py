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
    "1200 m",
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


def test_an_empty_register_has_nothing_to_report(run: Callable[..., Result]) -> None:
    result = run("register", "check")
    assert result.exit_code == 0
    assert "nothing to report" in result.output


def test_a_line_with_no_segments_fails_the_check(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run("register", "check")
    assert result.exit_code == 1
    assert "line has no segments" in result.output


def test_a_fully_described_line_passes(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    result = run("register", "check")
    assert result.exit_code == 0


def test_a_warning_does_not_fail_the_check_by_default(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post", "add", "TP-9", "--line", "AL-2", "--at", "39+37.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-9", "--on", "-905", "--off", "-1120")
    result = run("register", "check")
    assert result.exit_code == 0
    assert "off more negative than on" in result.output


def test_the_threshold_can_be_lowered(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post", "add", "TP-9", "--line", "AL-2", "--at", "39+37.00", "--installed", "1998-05-04"
    )
    run("post", "read", "TP-9", "--on", "-905", "--off", "-1120")
    assert run("register", "check", "--fail-on", "warning").exit_code == 1


def test_stats_count_the_rows(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    result = run("register", "stats")
    assert result.exit_code == 0
    assert "line" in result.output
    assert "rows in" in result.output
    assert "kB free" in result.output


def test_stats_on_an_empty_register_still_work(run: Callable[..., Result]) -> None:
    result = run("register", "stats")
    assert result.exit_code == 0
    assert "line" in result.output
    assert "rows in" in result.output


def test_a_backup_can_be_taken_and_used(run: Callable[..., Result], tmp_path: Path) -> None:
    run(*ADD_LINE)
    target = tmp_path / "backup.sqlite"
    result = run("register", "backup", str(target))
    assert result.exit_code == 0
    assert target.exists()
    assert target.stat().st_size > 0


def test_a_backup_leaves_no_part_file_behind(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    run(*ADD_LINE)
    target = tmp_path / "backup.sqlite"
    run("register", "backup", str(target))
    assert not (tmp_path / "backup.sqlite.part").exists()


def test_a_backup_onto_a_directory_is_refused(
    run: Callable[..., Result], tmp_path: Path
) -> None:
    run(*ADD_LINE)
    result = run("register", "backup", str(tmp_path))
    assert result.exit_code != 0


def test_a_vacuum_reports_what_it_gave_back(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run("register", "vacuum")
    assert result.exit_code == 0
    assert "kB reclaimed" in result.output
