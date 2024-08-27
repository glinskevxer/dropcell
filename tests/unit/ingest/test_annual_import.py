from __future__ import annotations

import datetime as dt

import pytest

from dropcell.electrodes import Electrode
from dropcell.errors import ConflictError
from dropcell.ingest.annual import import_annual
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.testpoints import TestPointRepository

NOW = dt.datetime(2025, 3, 20, 9, 0)

HEADER = "Test Post,Date,Lead,On,Off,Native,Half Cell,Surveyor,Comment\n"
ROWS = (
    "TP-114,2025-03-14,pipe,-1120,-905,-580,CSE-114,R Ellis,\n"
    "TP-115,2025-03-14,pipe,-1080,-870,,CSE-114,R Ellis,dog on the gate\n"
)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    posts = TestPointRepository(database)
    for code, station in (("TP-114", 1245.5), ("TP-115", 2400.0)):
        posts.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(station),
                leads=frozenset({LeadKind.PIPE, LeadKind.CASING}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
    return database


def test_a_clean_file_lands_every_row(register: Database) -> None:
    outcome = import_annual(register, HEADER + ROWS, now=NOW, source="annual.csv")
    assert outcome.written == 2
    assert outcome.clean
    assert ReadingRepository(register).count() == 2


def test_the_readings_carry_what_the_file_said(register: Database) -> None:
    import_annual(register, HEADER + ROWS, now=NOW)
    stored = ReadingRepository(register).for_point("TP-114")[0]
    assert stored.on_mv == pytest.approx(-1120.0)
    assert stored.native_mv == pytest.approx(-580.0)
    assert stored.technician == "R Ellis"
    assert stored.cell_serial == "CSE-114"


def test_an_empty_optional_cell_lands_as_nothing(register: Database) -> None:
    import_annual(register, HEADER + ROWS, now=NOW)
    stored = ReadingRepository(register).for_point("TP-115")[0]
    assert stored.native_mv is None
    assert stored.comment == "dog on the gate"


def test_the_run_is_written_to_the_ledger(register: Database) -> None:
    outcome = import_annual(register, HEADER + ROWS, now=NOW, source="annual.csv")
    assert outcome.run.kind == "annual"
    assert outcome.run.accepted == 2
    assert outcome.run.source == "annual.csv"


def test_the_same_file_is_refused_the_second_time(register: Database) -> None:
    import_annual(register, HEADER + ROWS, now=NOW)
    with pytest.raises(ConflictError):
        import_annual(register, HEADER + ROWS, now=NOW)


def test_a_row_naming_a_post_that_is_not_there_is_reported(register: Database) -> None:
    text = HEADER + "TP-999,2025-03-14,pipe,-1120,,,,,\n"
    outcome = import_annual(register, text, now=NOW)
    assert outcome.written == 0
    assert not outcome.clean
    assert "no test point" in outcome.reasons()[0]


def test_the_good_rows_of_a_mixed_file_still_land(register: Database) -> None:
    text = HEADER + ROWS + "TP-999,2025-03-14,pipe,-1120,,,,,\n"
    outcome = import_annual(register, text, now=NOW)
    assert outcome.written == 2
    assert len(outcome.skipped) == 1


def test_a_reading_already_in_the_register_is_skipped_not_refused(
    register: Database,
) -> None:
    import_annual(register, HEADER + ROWS, now=NOW)
    resent = HEADER + ROWS + "TP-114,2025-04-02,pipe,-1130,-910,,CSE-114,R Ellis,\n"
    outcome = import_annual(register, resent, now=NOW)
    assert outcome.written == 1
    assert len(outcome.skipped) == 2
    assert all("already in the register" in reason for reason in outcome.reasons())


def test_a_file_that_reads_one_lead_twice_in_a_day_keeps_the_first(
    register: Database,
) -> None:
    text = HEADER + ROWS + "TP-114,2025-03-14,pipe,-1000,,,,,\n"
    outcome = import_annual(register, text, now=NOW)
    assert outcome.written == 2
    assert "reads this lead twice" in outcome.reasons()[0]


def test_a_missing_lead_column_value_is_taken_as_the_pipe_lead(
    register: Database,
) -> None:
    text = HEADER + "TP-114,2025-03-14,,-1120,,,,,\n"
    import_annual(register, text, now=NOW)
    assert ReadingRepository(register).for_point("TP-114")[0].lead is LeadKind.PIPE


def test_a_casing_lead_lands_as_a_casing_reading(register: Database) -> None:
    text = HEADER + "TP-114,2025-03-14,casing,-560,,,,,\n"
    import_annual(register, text, now=NOW)
    assert ReadingRepository(register).for_point("TP-114")[0].lead is LeadKind.CASING


def test_a_lead_this_build_does_not_know_stops_the_import(register: Database) -> None:
    from dropcell.errors import IngestError

    text = HEADER + "TP-114,2025-03-14,antenna,-560,,,,,\n"
    with pytest.raises(IngestError):
        import_annual(register, text, now=NOW)


def test_the_electrode_the_crew_used_can_be_declared(register: Database) -> None:
    import_annual(register, HEADER + ROWS, now=NOW, electrode=Electrode.SCE)
    stored = ReadingRepository(register).for_point("TP-114")[0]
    assert stored.electrode is Electrode.SCE
    assert stored.on_cse_mv == pytest.approx(-1197.0)


def test_quarantined_rows_are_counted_on_the_outcome(register: Database) -> None:
    text = HEADER + ROWS + "TP-114,not a date,pipe,-1120,,,,,\n"
    outcome = import_annual(register, text, now=NOW)
    assert outcome.quarantined == 1
    assert not outcome.clean
    assert outcome.run.rejected == 1


def test_a_post_code_written_untidily_still_matches(register: Database) -> None:
    text = HEADER + "tp 114,2025-03-14,pipe,-1120,,,,,\n"
    outcome = import_annual(register, text, now=NOW)
    assert outcome.written == 1
