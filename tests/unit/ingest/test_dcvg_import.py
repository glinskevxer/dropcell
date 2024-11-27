from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, IngestError
from dropcell.ingest.dcvg import import_dcvg
from dropcell.store.database import Database
from dropcell.survey.dcvg import DcvgCategory

NOW = dt.datetime(2025, 3, 20, 9, 0)
HEADER = "Station,Date,Gradient,Total Shift,Anodic,Remark\n"

GOOD = (
    HEADER
    + "12+45.50,2025-03-14,40,400,,\n"
    + "18+00.00,2025-03-14,300,400,,at the road bore\n"
    + "22+10.00,2025-03-14,60,400,y,\n"
)


def test_a_clean_file_becomes_indications(database: Database) -> None:
    loaded = import_dcvg(database, GOOD, line_code="AL-2", now=NOW, source="dcvg.csv")
    assert loaded.found == 3
    assert loaded.clean
    assert loaded.run.kind == "dcvg"


def test_indications_come_back_worst_first(database: Database) -> None:
    loaded = import_dcvg(database, GOOD, line_code="AL-2", now=NOW)
    shares = [item.percent_ir for item in loaded.indications]
    assert shares == sorted(shares, reverse=True)
    assert loaded.indications[0].category is DcvgCategory.FOUR


def test_the_anodic_flag_comes_through(database: Database) -> None:
    loaded = import_dcvg(database, GOOD, line_code="AL-2", now=NOW)
    anodic = [item for item in loaded.indications if item.anodic]
    assert len(anodic) == 1
    assert anodic[0].station.format() == "22+10.00"


def test_remarks_come_through(database: Database) -> None:
    loaded = import_dcvg(database, GOOD, line_code="AL-2", now=NOW)
    remarks = [item.remark for item in loaded.indications if item.remark]
    assert remarks == ["at the road bore"]


def test_a_gradient_written_negative_is_taken_as_a_magnitude(
    database: Database,
) -> None:
    text = HEADER + "12+45.50,2025-03-14,-40,-400,,\n12+50.00,2025-03-14,40,400,,\n"
    loaded = import_dcvg(database, text, line_code="AL-2", now=NOW)
    assert loaded.indications[0].percent_ir == pytest.approx(10.0)


def test_a_gradient_larger_than_the_shift_is_set_aside(database: Database) -> None:
    text = GOOD + "30+00.00,2025-03-14,900,400,,\n"
    loaded = import_dcvg(database, text, line_code="AL-2", now=NOW)
    assert loaded.found == 3
    assert not loaded.clean
    assert "more gradient" in loaded.reasons()[0]


def test_a_row_with_no_date_can_take_a_default(database: Database) -> None:
    text = HEADER + "12+45.50,,40,400,,\n12+50.00,,60,400,,\n"
    loaded = import_dcvg(
        database, text, line_code="AL-2", now=NOW, default_found_on=dt.date(2025, 3, 14)
    )
    assert loaded.found == 2


def test_a_row_with_no_date_and_no_default_is_set_aside(database: Database) -> None:
    text = HEADER + "12+45.50,,40,400,,\n12+50.00,2025-03-14,60,400,,\n"
    loaded = import_dcvg(database, text, line_code="AL-2", now=NOW)
    assert loaded.found == 1
    assert "no date on the row" in loaded.reasons()[0]


def test_a_file_that_is_mostly_unreadable_is_refused(database: Database) -> None:
    text = HEADER + "12+45.50,2025-03-14,40,400,,\n" + "rubbish,rubbish,x,y,,\n" * 4
    with pytest.raises(IngestError) as caught:
        import_dcvg(database, text, line_code="AL-2", now=NOW)
    assert caught.value.detail["rejected"] == 4


def test_a_file_where_no_row_becomes_an_indication_is_refused(
    database: Database,
) -> None:
    text = HEADER + "12+45.50,,40,400,,\n12+50.00,,60,400,,\n"
    with pytest.raises(IngestError):
        import_dcvg(database, text, line_code="AL-2", now=NOW, minimum_acceptance=0.0)


def test_the_same_file_twice_is_a_conflict(database: Database) -> None:
    import_dcvg(database, GOOD, line_code="AL-2", now=NOW)
    with pytest.raises(ConflictError):
        import_dcvg(database, GOOD, line_code="AL-2", now=NOW)


def test_the_line_code_is_normalised_onto_every_indication(
    database: Database,
) -> None:
    loaded = import_dcvg(database, GOOD, line_code="al 2", now=NOW)
    assert {item.line_code for item in loaded.indications} == {"AL-2"}


def test_a_broken_row_is_quarantined_and_counted(database: Database) -> None:
    text = GOOD + "12+45.50,not a date,40,400,,\n"
    loaded = import_dcvg(database, text, line_code="AL-2", now=NOW, minimum_acceptance=0.5)
    assert loaded.quarantined == 1
    assert not loaded.clean
