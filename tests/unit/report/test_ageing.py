from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.report.ageing import age_findings, bucket_labels, bucket_of, render_ageing
from dropcell.stationing import Station, StationRange

TODAY = dt.date(2025, 3, 14)


def finding(days_old: int, **overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "code": f"F-2025-{days_old:03d}",
        "line_code": "AL-2",
        "kind": FindingKind.UNDER_CRITERION,
        "raised_on": TODAY - dt.timedelta(days=days_old),
        "extent": StationRange(Station(600.0), Station(660.0)),
        "summary": "under criterion",
    }
    kwargs.update(overrides)
    return Finding(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("days", "bucket"),
    [
        (0, 0),
        (29, 0),
        (30, 1),
        (89, 1),
        (90, 2),
        (179, 2),
        (180, 3),
        (364, 3),
        (365, 4),
        (4000, 4),
    ],
)
def test_the_buckets_are_closed_at_the_bottom(days: int, bucket: int) -> None:
    assert bucket_of(days) == bucket


def test_a_negative_age_is_refused() -> None:
    with pytest.raises(ValidationError):
        bucket_of(-1)


def test_there_is_a_label_for_every_bucket() -> None:
    assert len(bucket_labels()) == bucket_of(10_000) + 1


def test_open_findings_are_bucketed_by_kind() -> None:
    rows = age_findings(
        [finding(10), finding(200), finding(400, kind=FindingKind.COATING_DEFECT)],
        as_of=TODAY,
    )
    by_kind = {row.kind: row for row in rows}
    assert by_kind[FindingKind.UNDER_CRITERION].total == 2
    assert by_kind[FindingKind.COATING_DEFECT].stale == 1


def test_closed_findings_are_left_out() -> None:
    closed = finding(400, state=FindingState.CLEARED, closed_on=TODAY - dt.timedelta(days=10))
    assert age_findings([closed], as_of=TODAY) == []


def test_the_oldest_is_the_oldest_of_its_kind() -> None:
    rows = age_findings([finding(10), finding(400)], as_of=TODAY)
    assert rows[0].oldest_days == 400


def test_the_page_counts_the_stale_ones_separately() -> None:
    rows = age_findings([finding(10), finding(400), finding(500)], as_of=TODAY)
    rendered = render_ageing(rows, as_of=TODAY)
    assert "3 findings open, 2 of them for over a year" in rendered


def test_the_kinds_with_the_most_stale_findings_come_first() -> None:
    rows = age_findings(
        [finding(10), finding(400, kind=FindingKind.COATING_DEFECT)], as_of=TODAY
    )
    rendered = render_ageing(rows, as_of=TODAY)
    assert rendered.index("coating_defect") < rendered.index("under_criterion")


def test_an_empty_register_says_so() -> None:
    rendered = render_ageing([], as_of=TODAY)
    assert "nothing open" in rendered
    assert "0 findings open" in rendered


def test_the_line_can_be_named_on_the_title() -> None:
    rendered = render_ageing([], as_of=TODAY, line_code="AL-2")
    assert "Finding ageing, AL-2" in rendered


def test_empty_buckets_are_left_blank() -> None:
    rows = age_findings([finding(10)], as_of=TODAY)
    rendered = render_ageing(rows, as_of=TODAY)
    row = [line for line in rendered.splitlines() if "under_criterion" in line][0]
    assert row.count("1") >= 1
