from __future__ import annotations

import datetime as dt

import pytest

from dropcell.analysis.line import assess_line
from dropcell.config import Settings
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.report.annual import AnnualReport
from dropcell.schedule.policy import STANDARD_POLICY, AssetKind
from dropcell.schedule.register import AssetHistory, build_register
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository

YEAR_END = dt.date(2025, 12, 31)


@pytest.fixture
def register(database: Database, line: Line, segment: Segment) -> Database:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    posts = TestPointRepository(database)
    for code, metres in (("TP-1", 100.0), ("TP-2", 600.0), ("TP-3", 900.0)):
        posts.add(
            TestPoint(
                code=code,
                line_code="AL-2",
                station=Station(metres),
                leads=frozenset({LeadKind.PIPE}),
                installed_on=dt.date(1998, 5, 4),
            )
        )
    readings = ReadingRepository(database)
    readings.add(
        Reading(
            test_point_code="TP-1",
            lead=LeadKind.PIPE,
            taken_on=dt.date(2025, 5, 2),
            on_mv=-1120.0,
            off_mv=-905.0,
        )
    )
    readings.add(
        Reading(
            test_point_code="TP-2",
            lead=LeadKind.PIPE,
            taken_on=dt.date(2025, 5, 2),
            on_mv=-1020.0,
            off_mv=-780.0,
        )
    )
    return database


def finding(**overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "code": "F-2025-001",
        "line_code": "AL-2",
        "kind": FindingKind.UNDER_CRITERION,
        "raised_on": dt.date(2025, 5, 10),
        "extent": StationRange(Station(600.0), Station(660.0)),
        "summary": "sixty metres under criterion",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)  # type: ignore[arg-type]


def build(register: Database, findings: list[Finding]) -> AnnualReport:
    assessment = assess_line(register, "AL-2", as_of=YEAR_END)
    histories = [
        AssetHistory(
            code=item.code,
            kind=AssetKind.TEST_POINT,
            visits=(dt.date(2025, 5, 2),) if item.reading else (),
            in_service_from=dt.date(1998, 5, 4),
        )
        for item in assessment.posts
    ]
    return AnnualReport(
        year=2025,
        assessment=assessment,
        register=tuple(build_register(STANDARD_POLICY, histories, as_of=YEAR_END)),
        findings=tuple(findings),
        imports=(),
        settings=Settings(),
        prepared_on=dt.date(2026, 1, 15),
        prepared_by="R Ellis",
    )


def test_the_document_names_the_line_and_the_year(register: Database) -> None:
    rendered = build(register, []).render()
    assert "annual report 2025" in rendered
    assert "AL-2  Ashfield lateral" in rendered
    assert "prepared 2026-01-15 by R Ellis" in rendered


def test_the_thresholds_are_on_the_page(register: Database) -> None:
    rendered = build(register, []).render()
    assert "Measured against" in rendered
    assert "-850 mV instant off" in rendered
    assert "post reach" in rendered


def test_the_monitoring_figures_carry_their_denominators(register: Database) -> None:
    rendered = build(register, []).render()
    assert "of judged posts" in rendered
    assert "of asset and rule pairs" in rendered


def test_findings_are_split_into_raised_closed_and_carried(
    register: Database,
) -> None:
    report = build(
        register,
        [
            finding(),
            finding(
                code="F-2025-002",
                state=FindingState.CLEARED,
                closed_on=dt.date(2025, 9, 1),
            ),
            finding(code="F-2024-009", raised_on=dt.date(2024, 5, 10)),
        ],
    )
    assert [item.code for item in report.raised_this_year] == ["F-2025-001", "F-2025-002"]
    assert [item.code for item in report.closed_this_year] == ["F-2025-002"]
    assert [item.code for item in report.carried_forward] == ["F-2025-001", "F-2024-009"]


def test_a_year_with_nothing_left_undone_says_so(
    database: Database, line: Line, segment: Segment
) -> None:
    LineRepository(database).add(line)
    SegmentRepository(database).add(segment)
    TestPointRepository(database).add(
        TestPoint(
            code="TP-1",
            line_code="AL-2",
            station=Station(100.0),
            leads=frozenset({LeadKind.PIPE}),
            installed_on=dt.date(1998, 5, 4),
        )
    )
    ReadingRepository(database).add(
        Reading(
            test_point_code="TP-1",
            lead=LeadKind.PIPE,
            taken_on=dt.date(2025, 12, 2),
            on_mv=-1120.0,
            off_mv=-905.0,
        )
    )
    report = build(database, [])
    assert report.not_done() == ["nothing was left undone"]


def test_the_posts_nobody_read_are_named(register: Database) -> None:
    said = build(register, []).not_done()
    assert any("TP-3" in item for item in said)


def test_a_carried_finding_is_stated(register: Database) -> None:
    said = build(register, [finding()]).not_done()
    assert any("carried into the following year" in item for item in said)


def test_the_undone_list_is_on_the_rendered_page(register: Database) -> None:
    rendered = build(register, [finding()]).render()
    assert "What was not done" in rendered
    assert "TP-3" in rendered


def test_imports_are_counted_for_the_year_only(register: Database) -> None:
    from dropcell.store.imports import ImportRun

    report = build(register, [])
    this_year = ImportRun(
        run_id=1,
        content_hash="a",
        profile="annual",
        kind="annual",
        source="a.csv",
        imported_at=dt.datetime(2025, 5, 2, 9, 0),
        accepted=3,
        rejected=0,
    )
    last_year = ImportRun(
        run_id=2,
        content_hash="b",
        profile="annual",
        kind="annual",
        source="b.csv",
        imported_at=dt.datetime(2024, 5, 2, 9, 0),
        accepted=3,
        rejected=0,
    )
    import dataclasses

    with_imports = dataclasses.replace(report, imports=(this_year, last_year))
    assert [item.run_id for item in with_imports.imports_this_year] == [1]
    assert "1 survey files loaded" in with_imports.render()


def test_a_different_criterion_shows_up_on_the_page(register: Database) -> None:
    import dataclasses

    report = build(register, [])
    tight = dataclasses.replace(report, settings=Settings(protection_mv=-950.0))
    assert "-950 mV instant off" in tight.render()
