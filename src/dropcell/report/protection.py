"""The protection report, which is what a line looks like on one day.

Three groups, and keeping them apart is the whole design. Posts that met a
criterion. Posts that were judged and did not. Posts that could not be judged,
either because nobody has read them or because they sit on pipe no segment
describes.

The third group is the one that gets lost. Folded in with the passes it inflates
the rate, folded in with the failures it invents corrosion that nobody has
evidence of, and left out of the count entirely it disappears. It gets its own
table and its own line in the summary.

The criterion that carried each pass is printed. Two posts both reading
protected, one on the polarised criterion with sixty millivolts to spare and one
scraping through on decay, are not in the same condition, and a column that says
which is the cheapest way to show that.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.analysis.line import LineAssessment, PostAssessment
from dropcell.report.table import Column, Table

PROTECTED_COLUMNS = (
    Column("code", "Post"),
    Column("station", "Station", align="right"),
    Column("segment", "Segment"),
    Column("read", "Read"),
    Column("age", "Age d", align="right"),
    Column("off", "Off mV", align="right", format=".0f"),
    Column("criterion", "Met on", width=22),
    Column("margin", "Margin mV", align="right", format=".0f"),
)

FAILED_COLUMNS = (
    Column("code", "Post"),
    Column("station", "Station", align="right"),
    Column("segment", "Segment"),
    Column("read", "Read"),
    Column("off", "Off mV", align="right", format=".0f"),
    Column("short", "Short by mV", align="right", format=".0f"),
    Column("limits", "Limits broken", width=30),
)

UNJUDGED_COLUMNS = (
    Column("code", "Post"),
    Column("station", "Station", align="right"),
    Column("why", "Why", width=44),
)


def _station(item: PostAssessment, assessment: LineAssessment) -> str:
    return assessment.line.format_station(item.post.station)


def _met_criterion(item: PostAssessment) -> tuple[str, float | None]:
    if item.verdict is None or not item.verdict.met:
        return ("", None)
    best = max(
        item.verdict.met,
        key=lambda entry: entry.margin_mv if entry.margin_mv is not None else -1e9,
    )
    return (best.criterion, best.margin_mv)


def _why_unjudged(item: PostAssessment) -> str:
    if item.off_segment:
        return "sits on pipe no segment describes"
    if item.reading is None:
        return "never read"
    return "no criterion could be applied to the reading"


def protected_table(assessment: LineAssessment) -> Table:
    """Posts where a criterion was met."""
    table = Table(
        columns=PROTECTED_COLUMNS, title="Protected", empty_note="no post met a criterion"
    )
    for item in assessment.protected:
        criterion, margin = _met_criterion(item)
        table.add(
            code=item.code,
            station=_station(item, assessment),
            segment="" if item.segment is None else item.segment.code,
            read="" if item.reading is None else item.reading.taken_on.isoformat(),
            age=item.reading_age_days,
            off=None if item.reading is None else item.reading.off_cse_mv,
            criterion=criterion,
            margin=margin,
        )
    return table


def failed_table(assessment: LineAssessment) -> Table:
    """Posts that were judged and met nothing."""
    table = Table(
        columns=FAILED_COLUMNS, title="Under criterion", empty_note="nothing under criterion"
    )
    for item in assessment.under_criterion:
        verdict = item.verdict
        assert verdict is not None
        short = verdict.worst_margin_mv
        table.add(
            code=item.code,
            station=_station(item, assessment),
            segment="" if item.segment is None else item.segment.code,
            read="" if item.reading is None else item.reading.taken_on.isoformat(),
            off=None if item.reading is None else item.reading.off_cse_mv,
            short=None if short is None else -short,
            limits=", ".join(entry.criterion for entry in verdict.exceeded),
        )
    return table


def unjudged_table(assessment: LineAssessment) -> Table:
    """Posts no criterion could be applied to."""
    judged = {item.code for item in assessment.assessed}
    table = Table(
        columns=UNJUDGED_COLUMNS,
        title="Not assessed",
        empty_note="every post could be judged",
    )
    for item in assessment.posts:
        if item.code in judged:
            continue
        table.add(
            code=item.code,
            station=_station(item, assessment),
            why=_why_unjudged(item),
        )
    return table


@dataclass(frozen=True)
class ProtectionSummary:
    """The counts under the tables."""

    posts: int
    judged: int
    protected: int
    under_criterion: int
    unjudged: int
    stale: int
    rate: float

    def render(self) -> str:
        """Two lines for the bottom of the report."""
        return (
            f"{self.posts} posts, {self.judged} judged, {self.protected} protected, "
            f"{self.under_criterion} under criterion, {self.unjudged} not assessed\n"
            f"protection rate {self.rate:.1%} of judged posts, "
            f"{self.stale} verdicts rest on a reading over fifteen months old"
        )


def summarise(assessment: LineAssessment) -> ProtectionSummary:
    """Count what the assessment found."""
    return ProtectionSummary(
        posts=len(assessment.posts),
        judged=len(assessment.assessed),
        protected=len(assessment.protected),
        under_criterion=len(assessment.under_criterion),
        unjudged=len(assessment.posts) - len(assessment.assessed),
        stale=len(assessment.stale),
        rate=assessment.protection_rate,
    )


def render_protection(assessment: LineAssessment) -> str:
    """The whole report."""
    header = [
        f"Protection, {assessment.line.code} {assessment.line.name}",
        f"as at {assessment.as_of.isoformat()}",
        "",
    ]
    return "\n".join(
        [
            *header,
            failed_table(assessment).render(),
            "",
            unjudged_table(assessment).render(),
            "",
            protected_table(assessment).render(),
            "",
            summarise(assessment).render(),
        ]
    )
