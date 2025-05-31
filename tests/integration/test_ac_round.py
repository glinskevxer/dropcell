"""The case a potential only programme cannot see at all.

A line sharing a corridor with an overhead transmission line reads perfectly on
every criterion and corrodes at the coating defects anyway. The whole of the
evidence is on the coupons, and the point of this suite is that the register can
hold it, judge it, and put it in front of somebody without the potential figures
drowning it.

Everything here goes through the command line. The AC readings arrive as a file
because that is how they arrive, and the coupon has to have been installed
against a post that carries a coupon lead, which is the check that catches the
commonest data entry mistake in this part of the trade.
"""

from __future__ import annotations

from pathlib import Path

from tests.integration.conftest import Run

COUPON_FILE = (
    "Coupon,Date,On,Disconnected,DC Shunt,AC Shunt,AC Volts\n"
    "CP-1,2025-03-14,-1120,-905,0.001,0.15,6.4\n"
    "CP-2,2025-03-14,-1150,-960,0.001,0.0002,0.4\n"
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
        "1500 ohm-cm",
    )
    for code, station in (("TP-1", "10+00.00"), ("TP-2", "150+00.00")):
        ok(
            "post",
            "add",
            code,
            "--line",
            "AL-2",
            "--at",
            station,
            "--installed",
            "1998-05-04",
            "--lead",
            "pipe",
            "--lead",
            "coupon",
        )
    ok(
        "coupon",
        "add",
        "CP-1",
        "--post",
        "TP-1",
        "--shunt",
        "0.01",
        "--facing",
        "bottom",
        "--installed",
        "2019-06-03",
    )
    ok(
        "coupon",
        "add",
        "CP-2",
        "--post",
        "TP-2",
        "--shunt",
        "0.01",
        "--facing",
        "bottom",
        "--installed",
        "2019-06-03",
    )


def test_a_coupon_needs_a_post_that_carries_a_coupon_lead(run: Run, ok: Run) -> None:
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
    ok("post", "add", "TP-9", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04")
    ok(
        "coupon",
        "add",
        "CP-9",
        "--post",
        "TP-9",
        "--shunt",
        "0.01",
        "--installed",
        "2019-06-03",
    )
    check = run("register", "check", "--fail-on", "warning")
    assert check.exit_code == 1
    assert "coupon with no coupon lead" in check.output


def test_the_ac_file_loads_and_both_coupons_land(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "coupons-2025.csv"
    target.write_text(COUPON_FILE, encoding="utf-8")
    loaded = ok("coupon", "import", str(target))
    assert "2 readings written" in loaded.output
    assert "nothing but a connected potential" not in loaded.output


def test_the_potentials_alone_say_the_whole_line_is_fine(ok: Run, tmp_path: Path) -> None:
    build(ok)
    ok("post", "read", "TP-1", "--on", "-1120", "--off", "-905")
    ok("post", "read", "TP-2", "--on", "-1150", "--off", "-960")
    report = ok("report", "protection", "--line", "AL-2").output
    assert "protection rate 100.0%" in report


def test_the_coupons_say_one_of_them_is_not(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "coupons-2025.csv"
    target.write_text(COUPON_FILE, encoding="utf-8")
    ok("coupon", "import", str(target))
    status = ok("coupon", "status", "--line", "AL-2").output
    rows = {line.split()[0]: line for line in status.splitlines() if line.startswith("CP-")}
    assert rows["CP-1"].rstrip().endswith("yes")
    assert not rows["CP-2"].rstrip().endswith("yes")


def test_the_ac_density_is_on_the_page_in_the_unit_the_limits_use(
    ok: Run, tmp_path: Path
) -> None:
    build(ok)
    target = tmp_path / "coupons-2025.csv"
    target.write_text(COUPON_FILE, encoding="utf-8")
    ok("coupon", "import", str(target))
    status = ok("coupon", "status", "--line", "AL-2").output
    assert "AC A/m2" in status
    assert "150.0" in status


def test_a_finding_can_be_raised_against_what_the_coupon_found(ok: Run, tmp_path: Path) -> None:
    build(ok)
    target = tmp_path / "coupons-2025.csv"
    target.write_text(COUPON_FILE, encoding="utf-8")
    ok("coupon", "import", str(target))
    ok(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "ac_corrosion",
        "--from",
        "10+00.00",
        "--to",
        "12+00.00",
        "--summary",
        "CP-1 drawing 150 A per square metre of AC",
        "--due",
        "2025-06-14",
        "--by",
        "R Ellis",
    )
    register = ok("report", "exceptions", "--line", "AL-2").output
    assert "ac_corrosion" in register
    assert "F-2025-001" in register


def test_the_ac_finding_shows_up_in_the_ageing_page(ok: Run, tmp_path: Path) -> None:
    build(ok)
    ok(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "ac_corrosion",
        "--from",
        "10+00.00",
        "--summary",
        "AC corrosion at CP-1",
    )
    assert "ac_corrosion" in ok("report", "ageing", "--line", "AL-2").output


def test_a_second_reading_on_the_same_coupon_the_same_day_is_refused(
    run: Run, ok: Run, tmp_path: Path
) -> None:
    build(ok)
    target = tmp_path / "coupons-2025.csv"
    target.write_text(COUPON_FILE, encoding="utf-8")
    ok("coupon", "import", str(target))
    again = run("coupon", "read", "CP-1", "--on", "-1120", "--disconnected", "-905")
    assert again.exit_code == 4


def test_the_register_check_is_clean_once_the_leads_are_right(ok: Run) -> None:
    build(ok)
    assert ok("register", "check", "--fail-on", "warning").exit_code == 0
