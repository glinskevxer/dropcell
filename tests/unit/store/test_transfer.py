from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError, ValidationError
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.enums import LeadKind, LineStatus
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.migrations import migrate
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository
from dropcell.store.transfer import FORMAT, export_line, import_line

TODAY = dt.date(2025, 3, 14)


@pytest.fixture
def source(database: Database, line: Line, segment: Segment) -> Database:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    TestPointRepository(database).add(
        TestPoint(
            code="TP-1",
            line_code="AL-2",
            station=Station(600.0),
            leads=frozenset({LeadKind.PIPE, LeadKind.COUPON}),
            installed_on=dt.date(1998, 5, 4),
            description="beside the gate",
        )
    )
    ReadingRepository(database).add(
        Reading(
            test_point_code="TP-1",
            lead=LeadKind.PIPE,
            taken_on=TODAY,
            on_mv=-1120.0,
            off_mv=-905.0,
            technician="R Ellis",
        )
    )
    FindingRepository(database).raise_finding(
        Finding(
            code="F-2025-001",
            line_code="AL-2",
            kind=FindingKind.UNDER_CRITERION,
            raised_on=TODAY,
            extent=StationRange(Station(600.0), Station(660.0)),
            summary="under criterion",
            due_by=dt.date(2025, 6, 1),
        )
    )
    return database


def empty() -> Database:
    database = Database(":memory:")
    migrate(database)
    return database


def test_the_document_names_itself(source: Database) -> None:
    payload = export_line(source, "AL-2")
    assert payload["format"] == FORMAT
    assert payload["version"] == 1


def test_everything_hanging_off_the_line_travels(source: Database) -> None:
    payload = export_line(source, "AL-2")
    assert len(payload["segments"]) == 1
    assert len(payload["test_points"]) == 1
    assert len(payload["readings"]) == 1
    assert len(payload["findings"]) == 1


def test_a_line_that_is_not_there_cannot_be_exported(source: Database) -> None:
    with pytest.raises(NotFoundError):
        export_line(source, "ZZ-9")


def test_a_document_lands_in_an_empty_register(source: Database) -> None:
    payload = export_line(source, "AL-2")
    target = empty()
    imported = import_line(target, payload)
    assert imported.code == "AL-2"
    assert LineRepository(target).get("AL-2") == LineRepository(source).get("AL-2")


def test_the_segments_and_posts_arrive(source: Database) -> None:
    target = empty()
    import_line(target, export_line(source, "AL-2"))
    assert [item.code for item in SegmentRepository(target).for_line("AL-2")] == ["AL-2-004"]
    post = TestPointRepository(target).get("TP-1")
    assert post.leads == frozenset({LeadKind.PIPE, LeadKind.COUPON})
    assert post.description == "beside the gate"


def test_the_readings_arrive_with_their_numbers(source: Database) -> None:
    target = empty()
    import_line(target, export_line(source, "AL-2"))
    stored = ReadingRepository(target).for_point("TP-1")[0]
    assert stored.on_mv == pytest.approx(-1120.0)
    assert stored.off_mv == pytest.approx(-905.0)
    assert stored.technician == "R Ellis"


def test_the_findings_arrive_with_their_state(source: Database) -> None:
    FindingRepository(source).move(
        "F-2025-001", FindingState.CLEARED, on=dt.date(2025, 5, 2), actor="R Ellis"
    )
    target = empty()
    import_line(target, export_line(source, "AL-2"))
    stored = FindingRepository(target).get("F-2025-001")
    assert stored.state is FindingState.CLEARED
    assert stored.closed_on == dt.date(2025, 5, 2)


def test_a_retired_line_travels_with_its_status(source: Database) -> None:
    import dataclasses

    lines = LineRepository(source)
    lines.save(
        dataclasses.replace(
            lines.get("AL-2"),
            status=LineStatus.ABANDONED_IN_PLACE,
            retired_on=dt.date(2024, 1, 1),
        )
    )
    target = empty()
    import_line(target, export_line(source, "AL-2"))
    assert LineRepository(target).get("AL-2").status is LineStatus.ABANDONED_IN_PLACE


def test_a_line_already_in_the_target_is_refused(source: Database) -> None:
    payload = export_line(source, "AL-2")
    with pytest.raises(ConflictError):
        import_line(source, payload)


def test_a_document_that_is_not_one_is_refused() -> None:
    with pytest.raises(ValidationError):
        import_line(empty(), {"format": "something else", "version": 1})


def test_a_document_from_another_build_is_refused(source: Database) -> None:
    payload = export_line(source, "AL-2")
    payload["version"] = 99
    with pytest.raises(ValidationError) as caught:
        import_line(empty(), payload)
    assert caught.value.detail["expected"] == 1


def test_a_failed_import_leaves_nothing_behind(source: Database) -> None:
    payload = export_line(source, "AL-2")
    payload["test_points"][0]["leads"] = ["antenna"]
    target = empty()
    with pytest.raises(ValueError):
        import_line(target, payload)
    assert LineRepository(target).count() == 0


def test_nothing_derived_travels(source: Database) -> None:
    payload = export_line(source, "AL-2")
    reading = payload["readings"][0]
    assert set(reading) == {
        "test_point_code",
        "lead",
        "taken_on",
        "on_mv",
        "off_mv",
        "native_mv",
        "cell_serial",
        "technician",
        "comment",
    }
    assert "protection_rate" not in payload
    assert "verdict" not in payload
    assert not any("criterion_set" in item for item in payload["segments"])


def test_the_document_survives_a_round_trip_twice(source: Database) -> None:
    first = empty()
    import_line(first, export_line(source, "AL-2"))
    second = empty()
    import_line(second, export_line(first, "AL-2"))
    assert export_line(second, "AL-2") == export_line(source, "AL-2")
