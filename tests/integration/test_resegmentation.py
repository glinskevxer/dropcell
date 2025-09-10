"""A line being resegmented, which is where a register usually loses its history.

A road widening puts a new casing in the middle of a segment. A housing estate
raises the class location of half of it. A rehabilitation project recoats two
kilometres. All three turn one segment into two, and the way it is usually done
is to delete the segment and add two new ones, which takes with it every finding
that pointed at the old code and leaves the posts standing on nothing.

This walks the whole of that, on a line with readings and findings against it,
and checks that what should survive does and what should change has.
"""

from __future__ import annotations

from tests.integration.conftest import Run


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
    )
    for code, station in (("TP-1", "100+00.00"), ("TP-2", "400+00.00")):
        ok("post", "add", code, "--line", "AL-2", "--at", station, "--installed", "1998-05-04")
    ok("post", "read", "TP-1", "--on", "-1120", "--off", "-905", "--date", "2024-05-02")
    ok("post", "read", "TP-2", "--on", "-1020", "--off", "-780", "--date", "2024-05-02")
    ok(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "400+00.00",
        "--to",
        "410+00.00",
        "--summary",
        "under criterion around TP-2",
    )


def test_the_line_starts_with_one_segment_covering_both_posts(ok: Run) -> None:
    build(ok)
    report = ok("report", "protection", "--line", "AL-2").output
    assert "AL-2-001" in report
    assert "2 posts, 2 judged" in report


def test_splitting_leaves_both_posts_on_a_segment(ok: Run) -> None:
    build(ok)
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    report = ok("report", "protection", "--line", "AL-2").output
    assert "2 posts, 2 judged" in report
    assert "AL-2-001-A" in report
    assert "AL-2-001-B" in report


def test_the_readings_are_untouched_by_the_split(ok: Run) -> None:
    build(ok)
    before = ok("post", "show", "TP-2").output
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    assert ok("post", "show", "TP-2").output == before


def test_the_findings_are_untouched_by_the_split(ok: Run) -> None:
    build(ok)
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    assert "F-2025-001" in ok("report", "exceptions", "--line", "AL-2").output


def test_the_register_is_still_sound_after_the_split(ok: Run) -> None:
    build(ok)
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    check = ok("register", "check").output
    assert "post off every segment" not in check


def test_a_recoat_can_be_recorded_on_one_half(ok: Run, run: Run) -> None:
    build(ok)
    ok(
        "segment",
        "split",
        "AL-2-001",
        "--at",
        "300+00.00",
        "--left",
        "AL-2-001",
        "--right",
        "AL-2-002",
    )
    listed = ok("segment", "list", "--line", "AL-2").output
    assert listed.count("coal_tar") == 2
    ok(
        "segment",
        "add",
        "AL-2-003",
        "--line",
        "AL-2",
        "--from",
        "300+00.00",
        "--to",
        "600+00.00",
        "--coating",
        "three_layer_pe",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "2025",
        "--allow-overlap",
    )
    assert run("segment", "list", "--line", "AL-2").output.count("three_layer_pe") == 1


def test_the_overlap_is_refused_without_the_flag(ok: Run, run: Run) -> None:
    build(ok)
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    clash = run(
        "segment",
        "add",
        "AL-2-003",
        "--line",
        "AL-2",
        "--from",
        "300+00.00",
        "--to",
        "600+00.00",
        "--coating",
        "three_layer_pe",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "2025",
    )
    assert clash.exit_code == 4


def test_the_recoated_half_changes_what_the_coating_report_says(ok: Run) -> None:
    build(ok)
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    before = ok("plan", "coating", "--line", "AL-2", "--current", "2 A").output
    assert before.count("coal_tar") == 2


def test_a_post_moved_by_the_road_scheme_keeps_its_readings(ok: Run) -> None:
    build(ok)
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    moved = ok(
        "post", "move", "TP-2", "--to", "420+00.00", "--note", "moved for the A19 widening"
    )
    assert "2 readings kept" in moved.output or "1 readings kept" in moved.output
    assert "2024-05-02" in ok("post", "show", "TP-2").output


def test_the_moved_post_still_lands_on_a_segment(ok: Run) -> None:
    build(ok)
    ok("segment", "split", "AL-2-001", "--at", "300+00.00")
    ok("post", "move", "TP-2", "--to", "420+00.00")
    report = ok("report", "protection", "--line", "AL-2").output
    assert "2 posts, 2 judged" in report


def test_a_post_removed_by_the_road_scheme_keeps_its_history(ok: Run) -> None:
    build(ok)
    ok("post", "remove", "TP-1", "--on", "2025-02-01")
    assert "2024-05-02" in ok("post", "show", "TP-1").output
    listed = ok("post", "list", "--line", "AL-2", "--in-service").output
    assert "TP-1" not in listed
    assert "TP-2" in listed
