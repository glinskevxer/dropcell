"""An interference round, done the way a crew actually does one.

Everything a crew reads in a morning goes into the same register through the
same command line, and the point of this suite is that the four kinds of plant
end up on the same page, on the same monitoring register, and in the same
compliance figure. Each of those was wired separately and each of them was, at
some point, wired to only two of the four.
"""

from __future__ import annotations

from tests.integration.conftest import Run


def build_plant(ok: Run) -> None:
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
    )
    ok(
        "plant",
        "add-casing",
        "CS-12",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--length",
        "32 m",
        "--carries",
        "the A19",
        "--installed",
        "1998-05-04",
    )
    ok(
        "plant",
        "add-crossing",
        "XG-4",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--operator",
        "Vale Water",
        "--structure",
        "18 inch main",
    )
    ok(
        "plant",
        "add-bond",
        "BD-7",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--kind",
        "resistive",
        "--to",
        "Vale Water 18 inch main",
        "--design-current",
        "2 A",
        "--resistor",
        "0.03",
        "--installed",
        "2011-04-02",
        "--critical",
    )
    ok(
        "plant",
        "add-joint",
        "IJ-2",
        "--line",
        "AL-2",
        "--at",
        "1+00.00",
        "--kind",
        "flange_kit",
        "--separates",
        "Ashfield compressor station",
        "--installed",
        "2004-09-01",
        "--surge-protector",
    )


def test_the_whole_round_can_be_built_and_listed(ok: Run) -> None:
    build_plant(ok)
    listed = ok("plant", "list", "--line", "AL-2")
    for code in ("CS-12", "XG-4", "BD-7", "IJ-2"):
        assert code in listed.output


def test_everything_untested_is_on_the_interference_page(ok: Run) -> None:
    build_plant(ok)
    page = ok("report", "interference", "--line", "AL-2").output
    assert "4 pieces of plant, 4 never tested" in page


def test_everything_untested_is_also_overdue_on_the_compliance_page(
    ok: Run,
) -> None:
    build_plant(ok)
    page = ok("report", "compliance", "--line", "AL-2").output
    overdue = page.split("Falling due")[0]
    assert "CS-12" in overdue
    assert "BD-7" in overdue
    assert "IJ-2" in overdue


def test_an_ordinary_bond_is_not_on_the_monitoring_register(ok: Run) -> None:
    build_plant(ok)
    ok(
        "plant",
        "add-bond",
        "BD-8",
        "--line",
        "AL-2",
        "--at",
        "300+00.00",
        "--kind",
        "direct",
        "--to",
        "a fence",
        "--design-current",
        "1 A",
        "--installed",
        "2011-04-02",
    )
    page = ok("report", "compliance", "--line", "AL-2").output
    assert "BD-7" in page
    assert "BD-8" not in page


def test_a_morning_of_testing_clears_the_page(ok: Run) -> None:
    build_plant(ok)
    ok("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-560")
    ok("plant", "test-crossing", "XG-4", "--foreign-on", "-755", "--foreign-off", "-760")
    ok("plant", "test-bond", "BD-7", "--current", "2 A")
    ok("plant", "test-joint", "IJ-2", "--our-side", "-1120", "--other-side", "-420")
    page = ok("report", "interference", "--line", "AL-2").output
    assert "4 pieces of plant, 0 never tested, 0 needing work" in page


def test_the_same_morning_clears_the_compliance_page_too(ok: Run) -> None:
    build_plant(ok)
    ok("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-560")
    ok("plant", "test-crossing", "XG-4", "--foreign-on", "-755", "--foreign-off", "-760")
    ok("plant", "test-bond", "BD-7", "--current", "2 A")
    ok("plant", "test-joint", "IJ-2", "--our-side", "-1120", "--other-side", "-420")
    overdue = ok("report", "compliance", "--line", "AL-2").output.split("Falling due")[0]
    for code in ("CS-12", "BD-7", "IJ-2"):
        assert code not in overdue


def test_a_bad_morning_puts_three_of_them_back_on_the_page(ok: Run) -> None:
    build_plant(ok)
    ok("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-1116")
    ok("plant", "test-crossing", "XG-4", "--foreign-on", "-700", "--foreign-off", "-760")
    ok("plant", "test-bond", "BD-7", "--current", "0 A")
    ok("plant", "test-joint", "IJ-2", "--our-side", "-1120", "--other-side", "-420")
    page = ok("report", "interference", "--line", "AL-2").output
    assert "0 never tested, 3 needing work" in page
    assert "protection depends on this bond" in page


def test_the_joint_read_through_its_protector_is_not_called_shorted(ok: Run) -> None:
    build_plant(ok)
    through = ok("plant", "test-joint", "IJ-2", "--our-side", "-1120", "--other-side", "-1112")
    assert "proves nothing" in through.output
    page = ok("report", "interference", "--line", "AL-2").output
    assert "partial" in page
    assert "shorted" not in page


def test_the_history_of_a_crossing_survives_several_rounds(ok: Run) -> None:
    build_plant(ok)
    ok(
        "plant",
        "test-crossing",
        "XG-4",
        "--foreign-on",
        "-755",
        "--foreign-off",
        "-760",
        "--date",
        "2023-03-14",
    )
    ok(
        "plant",
        "test-crossing",
        "XG-4",
        "--foreign-on",
        "-700",
        "--foreign-off",
        "-760",
        "--date",
        "2024-03-14",
    )
    ok(
        "plant",
        "test-crossing",
        "XG-4",
        "--foreign-on",
        "-690",
        "--foreign-off",
        "-760",
        "--date",
        "2025-03-14",
    )
    history = ok("plant", "history", "XG-4", "--kind", "crossing").output
    assert history.count("harming_foreign") == 2
    assert "none" in history


def test_a_finding_can_be_raised_from_what_the_round_found(ok: Run) -> None:
    build_plant(ok)
    ok("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-1116")
    ok(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "shorted_casing",
        "--from",
        "40+00.00",
        "--to",
        "41+05.00",
        "--summary",
        "CS-12 reads as one structure with the carrier",
        "--due",
        "2025-06-12",
        "--by",
        "R Ellis",
    )
    assert "F-2025-001" in ok("report", "exceptions", "--line", "AL-2").output


def test_the_register_check_finds_nothing_wrong_with_any_of_it(ok: Run) -> None:
    build_plant(ok)
    ok("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-560")
    assert ok("register", "check").exit_code == 0
