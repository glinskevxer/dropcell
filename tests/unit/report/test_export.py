from __future__ import annotations

import csv
import datetime as dt
import io

import pytest

from dropcell.electrodes import Electrode
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.enums import LeadKind
from dropcell.model.reading import Reading
from dropcell.report.export import findings_csv, readings_csv, write_rows
from dropcell.stationing import Convention, Station, StationRange


def parse(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def finding(**overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "code": "F-2025-001",
        "line_code": "AL-2",
        "kind": FindingKind.UNDER_CRITERION,
        "raised_on": dt.date(2025, 1, 10),
        "extent": StationRange(Station(1200.0), Station(1260.0)),
        "summary": "sixty metres under criterion",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)  # type: ignore[arg-type]


def reading(**overrides: object) -> Reading:
    kwargs: dict[str, object] = {
        "test_point_code": "TP-114",
        "lead": LeadKind.PIPE,
        "taken_on": dt.date(2025, 3, 14),
        "on_mv": -1120.0,
        "off_mv": -905.0,
    }
    kwargs.update(overrides)
    return Reading(**kwargs)  # type: ignore[arg-type]


def test_an_empty_export_still_carries_its_header() -> None:
    rows = parse(findings_csv([]))
    assert rows == []
    assert findings_csv([]).splitlines()[0].startswith("code,line_code")


def test_a_finding_exports_every_column() -> None:
    row = parse(findings_csv([finding()]))[0]
    assert row["code"] == "F-2025-001"
    assert row["kind"] == "under_criterion"
    assert row["state"] == "open"
    assert row["length_m"] == "60.0"


def test_stations_go_out_both_ways() -> None:
    row = parse(findings_csv([finding()]))[0]
    assert row["start_station"] == "39+37.01"
    assert row["start_m"] == "1200.0"


def test_the_station_text_follows_the_convention() -> None:
    row = parse(findings_csv([finding()], convention=Convention.METRIC))[0]
    assert row["start_station"] == "1+200.0"
    assert row["start_m"] == "1200.0"


def test_a_missing_date_exports_as_an_empty_cell() -> None:
    row = parse(findings_csv([finding()]))[0]
    assert row["due_by"] == ""
    assert row["closed_on"] == ""


def test_a_closed_finding_carries_its_dates_and_name() -> None:
    closed = finding(
        state=FindingState.ACCEPTED,
        closed_on=dt.date(2025, 4, 1),
        closed_by="J Sowerby",
        closed_reason="being replaced",
    )
    row = parse(findings_csv([closed]))[0]
    assert row["closed_on"] == "2025-04-01"
    assert row["closed_by"] == "J Sowerby"


def test_a_summary_with_a_comma_survives_the_round_trip() -> None:
    row = parse(findings_csv([finding(summary="under criterion, road crossing")]))[0]
    assert row["summary"] == "under criterion, road crossing"


def test_readings_export_as_plain_numbers_with_the_unit_in_the_header() -> None:
    row = parse(readings_csv([reading()]))[0]
    assert row["on_mv"] == "-1120.0"
    assert row["off_mv"] == "-905.0"
    assert row["ir_drop_mv"] == "-215.0"


def test_a_reading_against_another_electrode_exports_against_copper_sulfate() -> None:
    row = parse(readings_csv([reading(on_mv=-1043.0, off_mv=-828.0, electrode=Electrode.SCE)]))[
        0
    ]
    assert float(row["on_mv"]) == pytest.approx(-1120.0)
    assert row["electrode"] == "sce"


def test_a_reading_with_no_off_exports_empty_cells() -> None:
    row = parse(readings_csv([reading(off_mv=None)]))[0]
    assert row["off_mv"] == ""
    assert row["ir_drop_mv"] == ""


def test_nothing_is_rounded_on_the_way_out() -> None:
    row = parse(readings_csv([reading(on_mv=-1120.4444)]))[0]
    assert row["on_mv"] == "-1120.4444"


def test_the_writer_turns_none_into_an_empty_cell() -> None:
    text = write_rows(("a", "b"), [(1, None)])
    assert text.splitlines()[1] == "1,"


def test_lines_end_the_same_way_on_every_platform() -> None:
    assert "\r" not in findings_csv([finding()])
