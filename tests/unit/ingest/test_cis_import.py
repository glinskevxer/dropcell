from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, IngestError
from dropcell.ingest.cis import build_survey, import_cis, infer_interval_m
from dropcell.ingest.profiles import CIS_PROFILE
from dropcell.ingest.reader import read_text
from dropcell.stationing import Convention, Station
from dropcell.store.database import Database
from dropcell.survey.cis import CisPoint

NOW = dt.datetime(2025, 3, 20, 9, 0)
TAKEN = dt.date(2025, 3, 14)

HEADER = "Station,P/S On,P/S Off,Remark\n"


def walk(count: int, step_ft: float = 5.0) -> str:
    rows = []
    for index in range(count):
        feet = index * step_ft
        major, minor = divmod(feet, 100)
        rows.append(f"{int(major)}+{minor:05.2f},-1120,-905,\n")
    return HEADER + "".join(rows)


def points(*metres: float) -> list[CisPoint]:
    return [CisPoint(station=Station(value), on_mv=-1120.0, off_mv=-905.0) for value in metres]


def test_the_interval_is_the_median_step() -> None:
    assert infer_interval_m(points(0.0, 1.5, 3.0, 4.5)) == pytest.approx(1.5)


def test_one_enormous_step_does_not_move_the_median() -> None:
    assert infer_interval_m(points(0.0, 1.5, 3.0, 400.0, 401.5)) == pytest.approx(1.5)


def test_too_few_steps_to_infer_an_interval_is_refused() -> None:
    with pytest.raises(IngestError):
        infer_interval_m(points(0.0, 1.5))


def test_a_file_where_nothing_moves_is_refused() -> None:
    with pytest.raises(IngestError):
        infer_interval_m(points(0.0, 0.0, 0.0))


def test_a_file_becomes_a_survey(database: Database) -> None:
    loaded = import_cis(
        database, walk(20), line_code="AL-2", taken_on=TAKEN, now=NOW, source="cis.csv"
    )
    assert loaded.steps == 20
    assert loaded.survey.line_code == "AL-2"
    assert loaded.survey.taken_on == TAKEN


def test_the_step_comes_off_the_file_when_it_is_not_given(database: Database) -> None:
    loaded = import_cis(database, walk(20), line_code="AL-2", taken_on=TAKEN, now=NOW)
    assert loaded.survey.nominal_interval_m == pytest.approx(5 * 0.3048)


def test_a_declared_step_beats_the_inferred_one(database: Database) -> None:
    loaded = import_cis(
        database,
        walk(20),
        line_code="AL-2",
        taken_on=TAKEN,
        now=NOW,
        nominal_interval_m=1.5,
    )
    assert loaded.survey.nominal_interval_m == pytest.approx(1.5)


def test_the_run_is_written_to_the_ledger(database: Database) -> None:
    loaded = import_cis(
        database, walk(20), line_code="AL-2", taken_on=TAKEN, now=NOW, source="cis.csv"
    )
    assert loaded.run.kind == "cis"
    assert loaded.run.accepted == 20


def test_the_same_file_is_refused_the_second_time(database: Database) -> None:
    import_cis(database, walk(20), line_code="AL-2", taken_on=TAKEN, now=NOW)
    with pytest.raises(ConflictError):
        import_cis(database, walk(20), line_code="AL-2", taken_on=TAKEN, now=NOW)


def test_rows_are_sorted_into_stationing_order(database: Database) -> None:
    text = HEADER + "0+10.00,-1120,-905,\n0+00.00,-1118,-902,\n0+05.00,-1130,-911,\n"
    loaded = import_cis(database, text, line_code="AL-2", taken_on=TAKEN, now=NOW)
    stations = [point.station.metres for point in loaded.survey.points]
    assert stations == sorted(stations)


def test_a_metric_file_reads_in_the_metric_convention(database: Database) -> None:
    text = HEADER + "1+000.0,-1120,-905,\n1+001.5,-1118,-902,\n1+003.0,-1130,-911,\n"
    loaded = import_cis(
        database,
        text,
        line_code="AL-2",
        taken_on=TAKEN,
        now=NOW,
        convention=Convention.METRIC,
    )
    assert loaded.survey.points[0].station.metres == pytest.approx(1000.0)
    assert loaded.survey.nominal_interval_m == pytest.approx(1.5)


def test_remarks_come_through_onto_the_points(database: Database) -> None:
    text = HEADER + "0+00.00,-1120,-905,gate\n0+05.00,-1118,-902,\n0+10.00,-1130,-911,\n"
    loaded = import_cis(database, text, line_code="AL-2", taken_on=TAKEN, now=NOW)
    assert loaded.survey.points[0].remark == "gate"


def test_a_file_with_one_readable_step_is_refused(database: Database) -> None:
    with pytest.raises(IngestError):
        import_cis(database, walk(1), line_code="AL-2", taken_on=TAKEN, now=NOW)


def test_the_refusal_says_how_many_rows_were_quarantined(database: Database) -> None:
    text = HEADER + "0+00.00,-1120,-905,\n0+05.00,rubbish,,\n"
    with pytest.raises(IngestError) as caught:
        import_cis(database, text, line_code="AL-2", taken_on=TAKEN, now=NOW)
    assert caught.value.detail["rejected"] == 1


def test_quarantined_rows_are_counted_on_a_survey_that_still_builds(
    database: Database,
) -> None:
    text = walk(20) + "9+99.00,rubbish,,\n"
    loaded = import_cis(database, text, line_code="AL-2", taken_on=TAKEN, now=NOW)
    assert loaded.quarantined == 1
    assert loaded.steps == 20


def test_building_a_survey_can_be_done_without_a_register() -> None:
    result = read_text(walk(20), CIS_PROFILE)
    survey = build_survey(result, line_code="al 2", taken_on=TAKEN, technician="R Ellis")
    assert survey.line_code == "AL-2"
    assert survey.technician == "R Ellis"
    assert survey.direction == "upstream"
