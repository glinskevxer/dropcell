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


def test_a_note_can_be_written_and_listed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    written = run(
        "note",
        "add",
        "--line",
        "AL-2",
        "--about",
        "TP-114",
        "the gate is locked and the farmer has the key",
    )
    assert written.exit_code == 0
    assert "note 1 written against TP-114" in written.output
    listed = run("note", "list", "--line", "AL-2")
    assert "the gate is locked" in listed.output


def test_an_access_note_says_it_will_stop_the_job(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    written = run(
        "note",
        "add",
        "--line",
        "AL-2",
        "--about",
        "TP-114",
        "--kind",
        "access",
        "no entry before October",
    )
    assert "likely to stop somebody" in written.output


def test_a_general_note_says_nothing_extra(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    written = run("note", "add", "--line", "AL-2", "--about", "TP-114", "repainted")
    assert "likely to stop" not in written.output


def test_a_note_can_carry_a_station(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(
        "note",
        "add",
        "--line",
        "AL-2",
        "--about",
        "the line",
        "--at",
        "40+00.00",
        "third party excavation seen here",
    )
    assert "40+00.00" in run("note", "list", "--line", "AL-2").output


def test_a_station_off_the_line_is_refused(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    result = run(
        "note", "add", "--line", "AL-2", "--about", "x", "--at", "9999+00.00", "something"
    )
    assert result.exit_code == 2


def test_notes_come_back_newest_first(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "--date", "2023-03-14", "older")
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "--date", "2025-03-14", "newer")
    listed = run("note", "list", "--line", "AL-2")
    assert listed.output.index("newer") < listed.output.index("older")


def test_notes_can_be_narrowed_by_subject(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "about the post")
    run("note", "add", "--line", "AL-2", "--about", "RU-3", "about the rectifier")
    listed = run("note", "list", "--line", "AL-2", "--about", "RU-3")
    assert "about the rectifier" in listed.output
    assert "about the post" not in listed.output


def test_notes_can_be_narrowed_by_kind(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "--kind", "damage", "ploughed")
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "repainted")
    listed = run("note", "list", "--line", "AL-2", "--kind", "damage")
    assert "ploughed" in listed.output
    assert "repainted" not in listed.output


def test_notes_can_be_narrowed_by_date(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "--date", "2023-03-14", "older")
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "--date", "2025-03-14", "newer")
    listed = run("note", "list", "--line", "AL-2", "--since", "2024-01-01")
    assert "newer" in listed.output
    assert "older" not in listed.output


def test_the_blocking_notes_can_be_pulled_out(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "--kind", "access", "locked")
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "repainted")
    listed = run("note", "list", "--line", "AL-2", "--blocking")
    assert "locked" in listed.output
    assert "repainted" not in listed.output


def test_a_line_with_nothing_written_down_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "nothing written down" in run("note", "list", "--line", "AL-2").output


def test_removing_a_note_asks_first(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "something")
    refused = run("note", "remove", "1", input_text="n\n")
    assert refused.exit_code != 0
    assert "something" in run("note", "list", "--line", "AL-2").output


def test_a_note_can_be_removed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run("note", "add", "--line", "AL-2", "--about", "TP-1", "something")
    removed = run("note", "remove", "1", input_text="y\n")
    assert removed.exit_code == 0
    assert "nothing written down" in run("note", "list", "--line", "AL-2").output


def test_removing_a_note_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("note", "remove", "99", input_text="y\n").exit_code == 3


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("note", "list", "--line", "ZZ-9").exit_code == 3
