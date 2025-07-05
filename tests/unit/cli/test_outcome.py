from __future__ import annotations

import datetime as dt

import click
import pytest
from click.testing import CliRunner

from dropcell.cli.outcome import report_dry_run, report_outcome
from dropcell.store.imports import ImportRun


def run(payload: ImportRun, **kwargs: object) -> str:
    @click.command()
    def command() -> None:
        report_outcome(payload, **kwargs)  # type: ignore[arg-type]

    return CliRunner().invoke(command).output


def make_run(**overrides: object) -> ImportRun:
    kwargs: dict[str, object] = {
        "run_id": 1,
        "content_hash": "abc",
        "profile": "annual",
        "kind": "annual",
        "source": "annual.csv",
        "imported_at": dt.datetime(2025, 3, 14, 9, 0),
        "accepted": 40,
        "rejected": 0,
    }
    kwargs.update(overrides)
    return ImportRun(**kwargs)  # type: ignore[arg-type]


def test_a_clean_import_says_what_landed() -> None:
    output = run(make_run(), landed=40, noun="rows")
    assert "40 rows written from annual.csv" in output
    assert "could not be read" not in output


def test_the_held_rows_are_always_reported() -> None:
    output = run(make_run(rejected=3), landed=37, noun="rows", quarantined=3)
    assert "3 rows could not be read" in output


def test_an_unnamed_input_still_prints_a_line() -> None:
    output = run(make_run(source=""), landed=1, noun="rows")
    assert "written from the input" in output


def test_the_noun_follows_what_was_loaded() -> None:
    output = run(make_run(), landed=2, noun="soundings")
    assert "2 soundings written" in output


def test_reasons_are_printed_one_to_a_line() -> None:
    output = run(
        make_run(), landed=1, noun="rows", reasons=("row 4: no post", "row 9: no post")
    )
    assert "  row 4: no post" in output
    assert "  row 9: no post" in output


def test_notes_come_after_the_reasons() -> None:
    output = run(
        make_run(),
        landed=1,
        noun="rows",
        reasons=("row 4: no post",),
        notes=("CP-1 carries nothing but a potential",),
    )
    assert output.index("row 4") < output.index("CP-1")


def test_a_dry_run_says_what_would_happen() -> None:
    @click.command()
    def command() -> None:
        report_dry_run(38, 2, ["row 4: bad date"])

    output = CliRunner().invoke(command).output
    assert "38 rows would read, 2 would be held" in output
    assert "  row 4: bad date" in output


def test_a_clean_dry_run_lists_nothing() -> None:
    @click.command()
    def command() -> None:
        report_dry_run(40, 0)

    output = CliRunner().invoke(command).output
    assert output.strip() == "40 rows would read, 0 would be held"


@pytest.mark.parametrize("noun", ["rows", "readings", "indications", "soundings"])
def test_every_command_uses_the_same_shape(noun: str) -> None:
    output = run(make_run(), landed=1, noun=noun)
    assert output.startswith(f"1 {noun} written from")
