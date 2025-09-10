"""How long findings have been sitting there, which is the figure that moves.

A count of open findings barely changes. Ten are raised and nine are closed and
the number stays where it was, and a programme can run like that for years while
the same four findings sit at the bottom of the list getting older.

Ageing buckets show that and nothing else does. The count in the oldest bucket
is the number of things nobody has managed to deal with, and it is the only
figure on any of these reports that cannot be improved by doing more surveys.

The buckets are wide on purpose. A finding that is ninety days old and one that
is a hundred and ten days old are the same finding, and a report with a bucket
per month invites an argument about which bucket rather than about the finding.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.findings.finding import Finding, FindingKind
from dropcell.report.table import Column, Table

BUCKET_EDGES = (30, 90, 180, 365)

AGEING_COLUMNS = (
    Column("kind", "Kind", width=20),
    Column("b0", "0 to 30 d", align="right"),
    Column("b1", "30 to 90", align="right"),
    Column("b2", "90 to 180", align="right"),
    Column("b3", "180 to 365", align="right"),
    Column("b4", "over a year", align="right"),
    Column("total", "Total", align="right"),
    Column("oldest", "Oldest d", align="right"),
)


def bucket_labels() -> list[str]:
    """What each bucket is called on the page, read off the columns.

    They were written out twice, here and in the column definitions, and the
    two had already stopped agreeing. Reading them off the columns means the
    page and the label list cannot drift again.
    """
    return [column.heading for column in AGEING_COLUMNS[1:6]]


def bucket_of(age_days: int) -> int:
    """Which bucket an age falls in."""
    if age_days < 0:
        raise ValidationError("a finding cannot be younger than nothing", age_days=age_days)
    for index, edge in enumerate(BUCKET_EDGES):
        if age_days < edge:
            return index
    return len(BUCKET_EDGES)


@dataclass(frozen=True)
class AgeingRow:
    """One kind of finding, bucketed by how long it has been open."""

    kind: FindingKind
    buckets: tuple[int, ...]
    oldest_days: int

    @property
    def total(self) -> int:
        """How many open findings of this kind there are."""
        return sum(self.buckets)

    @property
    def stale(self) -> int:
        """How many have been open longer than a year."""
        return self.buckets[-1]


def age_findings(findings: list[Finding], *, as_of: dt.date) -> list[AgeingRow]:
    """Bucket the open findings by kind and by how long they have been open."""
    counts: dict[FindingKind, list[int]] = {}
    oldest: dict[FindingKind, int] = {}
    for finding in findings:
        if not finding.is_open:
            continue
        age = finding.age_days(as_of)
        row = counts.setdefault(finding.kind, [0] * (len(BUCKET_EDGES) + 1))
        row[bucket_of(age)] += 1
        oldest[finding.kind] = max(oldest.get(finding.kind, 0), age)
    return [
        AgeingRow(kind=kind, buckets=tuple(row), oldest_days=oldest[kind])
        for kind, row in sorted(counts.items(), key=lambda item: str(item[0]))
    ]


def render_ageing(rows: list[AgeingRow], *, as_of: dt.date, line_code: str = "") -> str:
    """The whole page."""
    title = "Finding ageing" + (f", {line_code}" if line_code else "")
    table = Table(columns=AGEING_COLUMNS, title=title, empty_note="nothing open")
    totals = [0] * (len(BUCKET_EDGES) + 1)
    for row in sorted(rows, key=lambda item: (-item.stale, -item.total, str(item.kind))):
        table.add(
            kind=str(row.kind),
            b0=row.buckets[0] or None,
            b1=row.buckets[1] or None,
            b2=row.buckets[2] or None,
            b3=row.buckets[3] or None,
            b4=row.buckets[4] or None,
            total=row.total,
            oldest=row.oldest_days,
        )
        for index, count in enumerate(row.buckets):
            totals[index] += count
    stale = totals[-1]
    return "\n".join(
        [
            f"as at {as_of.isoformat()}",
            "",
            table.render(),
            "",
            f"{sum(totals)} findings open, {stale} of them for over a year",
        ]
    )
