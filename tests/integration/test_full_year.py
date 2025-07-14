"""One line, one year, every part of the tool, in the order it happens.

The unit suites hold each piece to its own behaviour and the other integration
suites walk one round each. This walks a whole year on one register and asserts
the things that can only go wrong when the pieces are put together: that a
survey loaded in March changes the compliance page in April, that a finding
raised off a gradient survey can be worked through to cleared, and that the
annual document at the end says what the year actually did.

It is deliberately the slowest test here. It is also the one that has caught
the most, because every failure it has found was a piece that worked perfectly
on its own.
"""

from __future__ import annotations

from pathlib import Path

from tests.integration.conftest import Run

ANNUAL = (
    "Test Post,Date,Lead,On,Off,Half Cell,Surveyor\n"
    "TP-101,2025-02-11,pipe,-1.180 V,-0.962 V,CSE-114,R Ellis\n"
    "TP-102,2025-02-11,pipe,-1.020 V,-0.804 V,CSE-114,R Ellis\n"
    "TP-103,2025-02-12,pipe,-1.190 V,-0.955 V,CSE-114,R Ellis\n"
)

DCVG = (
    "Station,Date,Gradient,Total Shift,Anodic\n"
    "150+00.00,2025-04-08,320,400,\n"
    "220+00.00,2025-04-08,40,400,\n"
)


def build(ok: Run) -> None:
    ok(
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
    ok(
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
        "1800 ohm-cm",
    )
    for code, station in (
        ("TP-101", "10+00.00"),
        ("TP-102", "150+00.00"),
        ("TP-103", "420+00.00"),
    ):
        ok("post", "add", code, "--line", "AL-2", "--at", station, "--installed", "1998-05-04")
    ok(
        "rectifier",
        "add-bed",
        "GB-1",
        "--kind",
        "deep_well",
        "--material",
        "high_silicon_iron",
        "--anodes",
        "12",
        "--mass",
        "20 kg",
        "--installed",
        "2004-09-01",
        "--design-current",
        "15 A",
    )
    ok(
        "rectifier",
        "add",
        "RU-1",
        "--line",
        "AL-2",
        "--at",
        "12+00.00",
        "--bed",
        "GB-1",
        "--rated-volts",
        "24",
        "--rated-amps",
        "20",
        "--installed",
        "2004-09-01",
    )


def rectifier_year(ok: Run, year: int) -> None:
    for month, day in ((1, 6), (3, 4), (5, 6), (7, 8), (9, 9), (11, 4)):
        ok(
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
            f"{year}-{month:02d}-{day:02d}",
        )


def test_a_new_register_reports_everything_as_never_done(ok: Run) -> None:
    build(ok)
    compliance = ok("report", "compliance", "--line", "AL-2").output
    assert "4 asset and rule pairs" in compliance
    assert "never" in compliance


def test_the_february_survey_moves_the_compliance_page(ok: Run, tmp_path: Path) -> None:
    build(ok)
    before = ok("report", "compliance", "--line", "AL-2").output.split("Falling due")[0]
    assert "TP-101" in before
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    ok("import", "annual", str(target), today="2025-02-14")
    after = ok("report", "compliance", "--line", "AL-2").output.split("Falling due")[0]
    assert "TP-101" not in after


def test_the_survey_shows_up_on_the_protection_page(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    ok("import", "annual", str(target), today="2025-02-14")
    report = ok("report", "protection", "--line", "AL-2").output
    assert "3 posts, 3 judged, 2 protected, 1 under criterion" in report


def test_a_gradient_survey_produces_a_dig_sheet(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "dcvg-2025.csv"
    target.write_text(DCVG, encoding="utf-8")
    sheet = ok("survey", "dcvg", str(target), "--line", "AL-2", today="2025-04-09").output
    assert "2 indications written" in sheet
    assert "Dig sheet, AL-2" in sheet
    assert "immediate" in sheet or "priority" in sheet


def test_a_finding_from_the_survey_can_be_worked_through(ok: Run) -> None:
    build(ok)
    ok(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "coating_defect",
        "--from",
        "150+00.00",
        "--to",
        "150+03.00",
        "--summary",
        "category four indication at the beck crossing",
        "--due",
        "2025-05-08",
        "--by",
        "R Ellis",
        today="2025-04-09",
    )
    ok(
        "work",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "excavation",
        "--summary",
        "dig and recoat at 150+00",
        "--finding",
        "F-2025-001",
        "--estimate",
        "4200",
        today="2025-04-10",
    )
    ok("work", "issue", "WO-2025-001", today="2025-04-11")
    done = ok("work", "done", "WO-2025-001", "--cost", "4600", today="2025-05-02")
    assert "stay open until a reading proves the work took" in done.output
    ok(
        "post",
        "read",
        "TP-102",
        "--on",
        "-1140",
        "--off",
        "-0.921 V",
        "--date",
        "2025-05-06",
        today="2025-05-06",
    )
    ok(
        "finding",
        "clear",
        "F-2025-001",
        "--by",
        "R Ellis",
        "--note",
        "re-read at -921 mV after the recoat",
        today="2025-05-07",
    )
    assert "no exceptions raised" in ok("report", "exceptions").output


def test_the_rectifier_year_clears_its_own_rule(ok: Run) -> None:
    build(ok)
    rectifier_year(ok, 2025)
    compliance = ok("report", "compliance", "--line", "AL-2", today="2025-12-31").output.split(
        "Falling due"
    )[0]
    assert "RU-1" not in compliance


def test_the_year_end_protection_reflects_the_repair(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    ok("import", "annual", str(target), today="2025-02-14")
    ok(
        "post",
        "read",
        "TP-102",
        "--on",
        "-1140",
        "--off",
        "-0.921 V",
        "--date",
        "2025-05-06",
        today="2025-05-06",
    )
    report = ok("report", "protection", "--line", "AL-2", today="2025-12-31").output
    assert "protection rate 100.0%" in report


def test_the_annual_document_says_what_the_year_did(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    ok("import", "annual", str(target), today="2025-02-14")
    rectifier_year(ok, 2025)
    ok(
        "post",
        "read",
        "TP-102",
        "--on",
        "-1140",
        "--off",
        "-0.921 V",
        "--date",
        "2025-05-06",
        today="2025-05-06",
    )
    document = ok(
        "report",
        "annual",
        "--line",
        "AL-2",
        "--year",
        "2025",
        "--by",
        "R Ellis",
        today="2026-01-15",
    ).output
    assert "annual report 2025" in document
    assert "1 survey files loaded" in document
    assert "protection rate 100.0%" in document
    assert "What was not done" in document


def test_the_year_end_estate_page_has_the_line_in_hand(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "annual-2025.csv"
    target.write_text(ANNUAL, encoding="utf-8")
    ok("import", "annual", str(target), today="2025-02-14")
    rectifier_year(ok, 2025)
    ok(
        "post",
        "read",
        "TP-102",
        "--on",
        "-1140",
        "--off",
        "-0.921 V",
        "--date",
        "2025-05-06",
        today="2025-05-06",
    )
    estate = ok("plan", "estate", today="2025-12-31").output
    assert "AL-2" in estate
    assert "in hand" in estate


def test_the_register_is_sound_at_the_end_of_it(ok: Run) -> None:
    build(ok)
    rectifier_year(ok, 2025)
    assert ok("register", "check").exit_code == 0
    stats = ok("register", "stats").output
    assert "rectifier_check" in stats
