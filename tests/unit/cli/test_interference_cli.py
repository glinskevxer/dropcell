from __future__ import annotations

from collections.abc import Callable

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


def test_the_four_kinds_of_plant_can_be_added_and_listed(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(
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
        "A19",
        "--installed",
        "1998-05-04",
    )
    run(
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
    run(
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
        "Vale Water main",
        "--design-current",
        "2 A",
        "--resistor",
        "0.03",
        "--installed",
        "2011-04-02",
        "--critical",
    )
    run(
        "plant",
        "add-joint",
        "IJ-2",
        "--line",
        "AL-2",
        "--at",
        "1+00.00",
        "--kind",
        "monolithic",
        "--separates",
        "compressor station",
        "--installed",
        "2004-09-01",
    )
    listed = run("plant", "list", "--line", "AL-2")
    assert listed.exit_code == 0
    for code in ("CS-12", "XG-4", "BD-7", "IJ-2"):
        assert code in listed.output
    assert "critical" in listed.output


def test_a_line_with_nothing_on_it_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "nothing else on this line" in run("plant", "list", "--line", "AL-2").output


def test_a_critical_bond_reports_its_shorter_interval(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    added = run(
        "plant",
        "add-bond",
        "BD-7",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--kind",
        "direct",
        "--to",
        "main",
        "--design-current",
        "2 A",
        "--installed",
        "2011-04-02",
        "--critical",
    )
    assert "every 75 days" in added.output


def test_a_resistive_bond_without_a_resistor_is_a_usage_error(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    result = run(
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
        "main",
        "--design-current",
        "2 A",
        "--installed",
        "2011-04-02",
    )
    assert result.exit_code == 2


def test_a_shorted_casing_is_reported_with_a_date(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-casing",
        "CS-12",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--installed",
        "1998-05-04",
    )
    result = run("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-1116")
    assert "metallic_short" in result.output
    assert "deal with by" in result.output


def test_a_clear_casing_needs_no_date(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-casing",
        "CS-12",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--installed",
        "1998-05-04",
    )
    result = run("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-560")
    assert "clear" in result.output
    assert "deal with by" not in result.output


def test_a_swing_test_names_whose_current_it_is(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
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
    ours = run(
        "plant", "test-crossing", "XG-4", "--foreign-on", "-700", "--foreign-off", "-760"
    )
    assert "harming_foreign" in ours.output
    assert "liability ours" in ours.output
    theirs = run(
        "plant",
        "test-crossing",
        "XG-4",
        "--foreign-on",
        "-700",
        "--foreign-off",
        "-760",
        "--theirs-interrupted",
        "--date",
        "2025-04-14",
    )
    assert "liability theirs" in theirs.output


def test_an_open_bond_is_reported(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-bond",
        "BD-7",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--kind",
        "direct",
        "--to",
        "main",
        "--design-current",
        "2 A",
        "--installed",
        "2011-04-02",
    )
    result = run("plant", "test-bond", "BD-7", "--current", "0 A")
    assert "open" in result.output


def test_a_healthy_bond_is_reported(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-bond",
        "BD-7",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--kind",
        "direct",
        "--to",
        "main",
        "--design-current",
        "2 A",
        "--installed",
        "2011-04-02",
    )
    result = run("plant", "test-bond", "BD-7", "--current", "2 A")
    assert "healthy" in result.output


def test_a_joint_read_through_its_surge_protector_proves_nothing(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(
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
        "station",
        "--installed",
        "2004-09-01",
        "--surge-protector",
    )
    through = run("plant", "test-joint", "IJ-2", "--our-side", "-1120", "--other-side", "-1112")
    assert "proves nothing" in through.output
    lifted = run(
        "plant",
        "test-joint",
        "IJ-2",
        "--our-side",
        "-1120",
        "--other-side",
        "-1112",
        "--protector-lifted",
        "--date",
        "2025-04-14",
    )
    assert "shorted" in lifted.output


def test_testing_something_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("plant", "test-bond", "BD-9", "--current", "1 A").exit_code == 3
    assert (
        run("plant", "test-casing", "CS-9", "--pipe-on", "-1", "--casing-on", "-1").exit_code
        == 3
    )


def test_plant_off_the_end_of_the_line_is_refused(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run(
        "plant",
        "add-casing",
        "CS-9",
        "--line",
        "AL-2",
        "--at",
        "9999+00.00",
        "--installed",
        "1998-05-04",
    )
    assert result.exit_code == 2


def test_a_test_is_kept_and_shows_up_in_the_history(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-casing",
        "CS-12",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--installed",
        "1998-05-04",
    )
    run(
        "plant",
        "test-casing",
        "CS-12",
        "--pipe-on",
        "-1120",
        "--casing-on",
        "-560",
        "--date",
        "2024-03-14",
    )
    run(
        "plant",
        "test-casing",
        "CS-12",
        "--pipe-on",
        "-1120",
        "--casing-on",
        "-1116",
        "--date",
        "2025-03-14",
    )
    history = run("plant", "history", "CS-12", "--kind", "casing")
    assert history.exit_code == 0
    assert "2024-03-14" in history.output
    assert "clear" in history.output
    assert "metallic_short" in history.output


def test_the_same_test_twice_on_one_day_is_a_conflict(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-casing",
        "CS-12",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--installed",
        "1998-05-04",
    )
    args = ("plant", "test-casing", "CS-12", "--pipe-on", "-1120", "--casing-on", "-560")
    run(*args)
    assert run(*args).exit_code == 4


def test_something_never_tested_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-bond",
        "BD-7",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--kind",
        "direct",
        "--to",
        "main",
        "--design-current",
        "2 A",
        "--installed",
        "2011-04-02",
    )
    assert "never tested" in run("plant", "history", "BD-7", "--kind", "bond").output


def test_a_bond_history_carries_its_verdicts(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-bond",
        "BD-7",
        "--line",
        "AL-2",
        "--at",
        "80+00.00",
        "--kind",
        "direct",
        "--to",
        "main",
        "--design-current",
        "2 A",
        "--installed",
        "2011-04-02",
    )
    run("plant", "test-bond", "BD-7", "--current", "2 A", "--date", "2024-03-14")
    run("plant", "test-bond", "BD-7", "--current", "0 A", "--date", "2025-03-14")
    history = run("plant", "history", "BD-7", "--kind", "bond")
    assert "healthy" in history.output
    assert "open" in history.output


def test_a_crossing_history_carries_its_swings(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
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
    run(
        "plant",
        "test-crossing",
        "XG-4",
        "--foreign-on",
        "-700",
        "--foreign-off",
        "-760",
        "--date",
        "2025-03-14",
    )
    history = run("plant", "history", "XG-4", "--kind", "crossing")
    assert "+60 mV swing" in history.output
    assert "harming_foreign" in history.output


def test_a_joint_history_carries_its_tests(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "plant",
        "add-joint",
        "IJ-2",
        "--line",
        "AL-2",
        "--at",
        "1+00.00",
        "--kind",
        "monolithic",
        "--separates",
        "station",
        "--installed",
        "2004-09-01",
    )
    run("plant", "test-joint", "IJ-2", "--our-side", "-1120", "--other-side", "-420")
    history = run("plant", "history", "IJ-2", "--kind", "joint")
    assert "isolating" in history.output


def test_a_history_for_something_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("plant", "history", "CS-9", "--kind", "casing").exit_code == 3
