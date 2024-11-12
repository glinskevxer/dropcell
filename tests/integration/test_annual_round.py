"""One year of the ordinary work, done through the command line."""

from __future__ import annotations

from pathlib import Path

from tests.integration.conftest import Run

ANNUAL = (
    "Test Post,Date,Lead,On,Off,Half Cell,Surveyor\n"
    "TP-101,2025-02-11,pipe,-1.180 V,-0.962 V,CSE-114,R Ellis\n"
    "TP-102,2025-02-11,pipe,-1.020 V,-0.804 V,CSE-114,R Ellis\n"
    "TP-103,2025-02-12,pipe,-1.310 V,-1.244 V,CSE-114,R Ellis\n"
)


def test_a_new_register_starts_empty(ok: Run) -> None:
    ok("init")
    assert "no lines in the register" in ok("line", "list").output


def test_the_plant_can_be_built_entirely_from_the_command_line(
    line_built: Run,
) -> None:
    shown = line_built("line", "show", "AL-2")
    assert "AL-2-001" in shown.output
    assert "AL-2-002" in shown.output
    assert "TP-101" in line_built("post", "list", "--line", "AL-2").output
    assert "RU-1" in line_built("rectifier", "status", "--line", "AL-2").output


def test_an_annual_survey_lands_and_shows_up_everywhere(
    line_built: Run, tmp_path: Path
) -> None:
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    loaded = line_built("import", "annual", str(target))
    assert "3 rows written" in loaded.output
    assert "2025-02-11" in line_built("post", "show", "TP-101").output
    assert "annual-2025.csv" in line_built("import", "runs").output


def test_the_protection_report_separates_the_three_outcomes(
    line_built: Run, tmp_path: Path
) -> None:
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    line_built("import", "annual", str(target))
    report = line_built("report", "protection", "--line", "AL-2").output
    assert "TP-101" in report
    assert "TP-102" in report
    assert "3 posts, 3 judged" in report


def test_the_post_that_missed_the_criterion_is_named(line_built: Run, tmp_path: Path) -> None:
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    line_built("import", "annual", str(target))
    report = line_built("report", "protection", "--line", "AL-2").output
    under = report.split("Under criterion")[1].split("Not assessed")[0]
    assert "TP-102" in under
    assert "TP-101" not in under


def test_the_over_protected_post_is_flagged_without_losing_its_pass(
    line_built: Run, tmp_path: Path
) -> None:
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    line_built("import", "annual", str(target))
    report = line_built("report", "protection", "--line", "AL-2").output
    protected = report.split("Protected")[1]
    assert "TP-103" in protected


def test_a_post_read_this_year_drops_off_the_overdue_table(
    line_built: Run, tmp_path: Path
) -> None:
    before = line_built("report", "compliance", "--line", "AL-2").output
    assert "TP-101" in before.split("Falling due")[0]
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    line_built("import", "annual", str(target))
    after = line_built("report", "compliance", "--line", "AL-2").output
    overdue = after.split("Falling due")[0]
    assert "TP-101" not in overdue
    assert "TP-102" not in overdue


def test_a_year_with_no_visit_in_it_stays_on_the_record(
    line_built: Run, tmp_path: Path
) -> None:
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    line_built("import", "annual", str(target))
    report = line_built("report", "compliance", "--line", "AL-2").output
    assert "required visits" in report


def test_the_rectifier_is_overdue_because_nobody_has_checked_it(
    line_built: Run,
) -> None:
    report = line_built("report", "compliance", "--line", "AL-2").output
    assert "RU-1" in report
    assert "never" in report


def test_checking_the_rectifier_six_times_clears_its_year(line_built: Run) -> None:
    for month, day in ((1, 6), (3, 4), (5, 6), (7, 8), (9, 9), (11, 4)):
        line_built(
            "rectifier",
            "check",
            "RU-1",
            "--volts",
            "18.5",
            "--amps",
            "12.4",
            "--coarse",
            "3",
            "--fine",
            "2",
            "--date",
            f"2024-{month:02d}-{day:02d}",
        )
    report = line_built("report", "compliance", "--line", "AL-2", today="2025-01-06").output
    assert "RU-1" not in report.split("Falling due")[0]


def test_a_finding_raised_by_hand_reaches_the_register_and_the_export(
    line_built: Run,
) -> None:
    line_built(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "150+00.00",
        "--to",
        "160+00.00",
        "--summary",
        "under criterion at the beck crossing",
        "--due",
        "2025-06-01",
        "--by",
        "R Ellis",
    )
    assert "F-2025-001" in line_built("report", "exceptions").output
    assert "F-2025-001" in line_built("report", "export", "findings", "--line", "AL-2").output


def test_a_finding_can_be_worked_through_to_cleared(line_built: Run) -> None:
    line_built(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "150+00.00",
        "--summary",
        "under criterion",
    )
    line_built("finding", "schedule", "F-2025-001", "--by", "J Sowerby")
    line_built(
        "finding",
        "clear",
        "F-2025-001",
        "--by",
        "R Ellis",
        "--note",
        "anode string added, re-read at -0.940 V",
    )
    assert "no exceptions raised" in line_built("report", "exceptions").output
    trail = line_built("finding", "show", "F-2025-001").output
    assert "anode string added" in trail
    assert trail.count("2025-03-14") >= 3
