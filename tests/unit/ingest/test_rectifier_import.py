from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError
from dropcell.ingest.rectifier import import_rectifier_checks
from dropcell.model.enums import AnodeMaterial, GroundbedKind
from dropcell.model.groundbed import Groundbed
from dropcell.model.line import Line
from dropcell.model.rectifier import Rectifier
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.rectifiers import (
    GroundbedRepository,
    RectifierCheckRepository,
    RectifierRepository,
)

NOW = dt.datetime(2025, 3, 20, 9, 0)
HEADER = "Rectifier,Date,Volts,Amps,Coarse,Fine,Hours,Tech,Comment\n"


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    GroundbedRepository(database).add(
        Groundbed(
            code="GB-3",
            kind=GroundbedKind.DEEP_WELL,
            material=AnodeMaterial.HIGH_SILICON_IRON,
            anode_count=10,
            anode_mass_kg=20.0,
            installed_on=dt.date(2004, 9, 1),
            design_current_a=15.0,
        )
    )
    RectifierRepository(database).add(
        Rectifier(
            tag="RU-3",
            line_code="AL-2",
            station=Station(4210.0),
            groundbed_code="GB-3",
            rated_voltage_v=24.0,
            rated_current_a=20.0,
            coarse_taps=5,
            fine_taps=4,
            installed_on=dt.date(2004, 9, 1),
        )
    )
    return database


def test_a_clean_sheet_lands_every_row(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,41233,R Ellis,\n"
    outcome = import_rectifier_checks(register, text, now=NOW, source="tr.csv")
    assert outcome.written == 1
    assert outcome.clean
    stored = RectifierCheckRepository(register).for_unit("RU-3")[0]
    assert stored.output_voltage_v == pytest.approx(18.5)
    assert stored.hour_meter == pytest.approx(41233.0)


def test_the_run_is_written_to_the_ledger(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,,,\n"
    outcome = import_rectifier_checks(register, text, now=NOW)
    assert outcome.run.kind == "rectifier"


def test_the_same_sheet_is_refused_the_second_time(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,,,\n"
    import_rectifier_checks(register, text, now=NOW)
    with pytest.raises(ConflictError):
        import_rectifier_checks(register, text, now=NOW)


def test_a_unit_that_is_not_in_the_register_is_reported(register: Database) -> None:
    text = HEADER + "RU-9,2025-01-06,18.5,12.4,3,2,,,\n"
    outcome = import_rectifier_checks(register, text, now=NOW)
    assert outcome.written == 0
    assert "no rectifier" in outcome.reasons()[0]


def test_blank_taps_are_taken_from_the_previous_check(register: Database) -> None:
    first = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,,,\n"
    import_rectifier_checks(register, first, now=NOW)
    second = HEADER + "RU-3,2025-03-14,18.6,12.5,,,,,\n"
    outcome = import_rectifier_checks(register, second, now=NOW)
    assert outcome.written == 1
    stored = RectifierCheckRepository(register).latest("RU-3")
    assert stored is not None
    assert (stored.coarse_tap, stored.fine_tap) == (3, 2)


def test_blank_taps_carry_forward_inside_one_file(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,,,\n" + "RU-3,2025-03-14,18.6,12.5,,,,,\n"
    outcome = import_rectifier_checks(register, text, now=NOW)
    assert outcome.written == 2
    stored = RectifierCheckRepository(register).latest("RU-3")
    assert stored is not None
    assert stored.coarse_tap == 3


def test_blank_taps_on_a_unit_never_read_are_reported_not_guessed(
    register: Database,
) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,,,,,\n"
    outcome = import_rectifier_checks(register, text, now=NOW)
    assert outcome.written == 0
    assert "nothing earlier to take them from" in outcome.reasons()[0]


def test_a_tap_pair_that_is_not_on_the_board_is_reported(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,9,2,,,\n"
    outcome = import_rectifier_checks(register, text, now=NOW)
    assert outcome.written == 0
    assert "not on this unit's board" in outcome.reasons()[0]


def test_a_check_already_in_the_register_is_skipped(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,,,\n"
    import_rectifier_checks(register, text, now=NOW)
    resent = text + "RU-3,2025-03-14,18.6,12.5,3,2,,,\n"
    outcome = import_rectifier_checks(register, resent, now=NOW)
    assert outcome.written == 1
    assert "already in the register" in outcome.reasons()[0]


def test_a_sheet_that_reads_one_unit_twice_in_a_day_keeps_the_first(
    register: Database,
) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,,,\n" + "RU-3,2025-01-06,18.9,12.9,3,2,,,\n"
    outcome = import_rectifier_checks(register, text, now=NOW)
    assert outcome.written == 1
    assert "twice on one day" in outcome.reasons()[0]


def test_a_current_in_milliamps_lands_in_amps(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,250 mA,3,2,,,\n"
    import_rectifier_checks(register, text, now=NOW)
    stored = RectifierCheckRepository(register).for_unit("RU-3")[0]
    assert stored.output_current_a == pytest.approx(0.25)


def test_a_broken_row_is_quarantined_and_counted(register: Database) -> None:
    text = HEADER + "RU-3,2025-01-06,18.5,12.4,3,2,,,\nRU-3,not a date,1,1,3,2,,,\n"
    outcome = import_rectifier_checks(register, text, now=NOW)
    assert outcome.written == 1
    assert outcome.quarantined == 1
