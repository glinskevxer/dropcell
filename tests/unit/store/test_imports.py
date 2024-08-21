from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile
from dropcell.ingest.reader import read_text
from dropcell.store.database import Database
from dropcell.store.imports import ImportLedger

NOW = dt.datetime(2025, 3, 14, 9, 30)

PROFILE = MappingProfile(
    name="acme_cis",
    columns=(
        ColumnMapping("station", FieldType.STATION, ("Station",)),
        ColumnMapping("on_mv", FieldType.POTENTIAL, ("P/S On",)),
    ),
)

GOOD = "Station,P/S On\n0+00.00,-1120\n0+02.50,-1118\n"
DIRTY = "Station,P/S On\n0+00.00,-1120\n0+02.50,rubbish\n"


@pytest.fixture
def ledger(database: Database) -> ImportLedger:
    return ImportLedger(database)


def test_a_run_is_recorded_with_its_counts(ledger: ImportLedger) -> None:
    result = read_text(GOOD, PROFILE, source="cis.csv")
    run = ledger.record(result, kind="cis", now=NOW)
    assert run.accepted == 2
    assert run.rejected == 0
    assert run.total == 2
    assert run.source == "cis.csv"


def test_a_recorded_run_can_be_read_back(ledger: ImportLedger) -> None:
    run = ledger.record(read_text(GOOD, PROFILE), kind="cis", now=NOW)
    assert ledger.get(run.run_id) == run


def test_a_run_number_that_is_not_there_is_refused(ledger: ImportLedger) -> None:
    with pytest.raises(NotFoundError):
        ledger.get(99)


def test_the_same_bytes_are_refused_the_second_time(ledger: ImportLedger) -> None:
    ledger.record(read_text(GOOD, PROFILE, source="a.csv"), kind="cis", now=NOW)
    with pytest.raises(ConflictError) as caught:
        ledger.record(read_text(GOOD, PROFILE, source="b.csv"), kind="cis", now=NOW)
    assert caught.value.detail["source"] == "a.csv"


def test_the_duplicate_refusal_names_when_it_first_landed(ledger: ImportLedger) -> None:
    ledger.record(read_text(GOOD, PROFILE), kind="cis", now=NOW)
    with pytest.raises(ConflictError) as caught:
        ledger.record(read_text(GOOD, PROFILE), kind="cis", now=NOW)
    assert caught.value.detail["imported_at"].startswith("2025-03-14T09:30")


def test_a_file_with_one_reading_changed_is_a_different_file(
    ledger: ImportLedger,
) -> None:
    ledger.record(read_text(GOOD, PROFILE), kind="cis", now=NOW)
    changed = GOOD.replace("-1118", "-1119")
    ledger.record(read_text(changed, PROFILE), kind="cis", now=NOW)
    assert ledger.count() == 2


def test_the_ledger_answers_whether_it_has_seen_a_hash(ledger: ImportLedger) -> None:
    result = read_text(GOOD, PROFILE)
    assert not ledger.already_seen(result.content_hash)
    ledger.record(result, kind="cis", now=NOW)
    assert ledger.already_seen(result.content_hash)


def test_quarantined_rows_are_kept_with_their_run(ledger: ImportLedger) -> None:
    run = ledger.record(read_text(DIRTY, PROFILE), kind="cis", now=NOW)
    held = ledger.quarantine_for(run.run_id)
    assert len(held) == 1
    assert held[0].row_number == 3
    assert held[0].raw == ("0+02.50", "rubbish")
    assert held[0].errors[0].field_name == "on_mv"
    assert "on_mv" in held[0].summary


def test_a_clean_run_has_nothing_in_quarantine(ledger: ImportLedger) -> None:
    run = ledger.record(read_text(GOOD, PROFILE), kind="cis", now=NOW)
    assert ledger.quarantine_for(run.run_id) == []


def test_recent_runs_come_back_newest_first(ledger: ImportLedger) -> None:
    ledger.record(read_text(GOOD, PROFILE, source="old.csv"), kind="cis", now=NOW)
    later = NOW + dt.timedelta(days=1)
    ledger.record(read_text(DIRTY, PROFILE, source="new.csv"), kind="cis", now=later)
    assert [run.source for run in ledger.recent()] == ["new.csv", "old.csv"]


def test_recent_runs_can_be_narrowed_to_one_kind(ledger: ImportLedger) -> None:
    ledger.record(read_text(GOOD, PROFILE, source="a.csv"), kind="cis", now=NOW)
    ledger.record(read_text(DIRTY, PROFILE, source="b.csv"), kind="rectifier", now=NOW)
    assert [run.source for run in ledger.recent(kind="rectifier")] == ["b.csv"]


def test_the_limit_is_honoured(ledger: ImportLedger) -> None:
    for index in range(4):
        text = GOOD + f"0+0{index}.10,-1100\n"
        ledger.record(read_text(text, PROFILE), kind="cis", now=NOW)
    assert len(ledger.recent(limit=2)) == 2


def test_deleting_a_run_takes_its_quarantine_with_it(
    database: Database, ledger: ImportLedger
) -> None:
    run = ledger.record(read_text(DIRTY, PROFILE), kind="cis", now=NOW)
    database.execute("DELETE FROM import_run WHERE id = ?", (run.run_id,))
    assert database.scalar("SELECT count(*) FROM import_quarantine") == 0
