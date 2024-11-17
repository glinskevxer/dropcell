"""The numbers that go on one slide, and what each of them is not.

Every figure here has a denominator that somebody will quote without, so each
one carries it. Protection rate is over posts that could be judged. Compliance
rate is over asset and rule pairs. Coverage is over line length. Three
percentages that look alike and are measured over three different things, and
mixing them up is how a programme reports ninety percent while a third of the
line has never been walked.

There is one figure here that is not a rate and it is the one worth reading
first. The count of posts nobody has ever read is a whole number, it cannot be
diluted by a large denominator, and it does not improve when somebody adds more
posts.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.analysis.coverage import CoverageReport
from dropcell.analysis.line import LineAssessment
from dropcell.findings.finding import Finding
from dropcell.report.table import Column, Table
from dropcell.schedule.register import DueItem, compliance_rate, overdue

KPI_COLUMNS = (
    Column("figure", "Figure", width=34),
    Column("value", "Value", align="right"),
    Column("over", "Measured over", width=34),
)


@dataclass(frozen=True)
class Kpis:
    """One line's programme, on one page."""

    line_code: str
    as_of: dt.date
    posts: int
    judged_posts: int
    protected_posts: int
    never_read_posts: int
    stale_posts: int
    protection_rate: float
    compliance_rate: float
    overdue_items: int
    covered_share: float
    longest_gap_m: float
    open_findings: int
    overdue_findings: int
    finding_length_m: float

    def rows(self) -> list[tuple[str, str, str]]:
        """Every figure with its value and its denominator."""
        return [
            ("posts on the line", f"{self.posts}", "count"),
            ("posts never read", f"{self.never_read_posts}", "count, not a rate"),
            ("posts read over 15 months ago", f"{self.stale_posts}", "count"),
            (
                "protection rate",
                f"{self.protection_rate:.1%}",
                f"{self.judged_posts} posts that could be judged",
            ),
            (
                "monitoring compliance",
                f"{self.compliance_rate:.1%}",
                "asset and rule pairs",
            ),
            ("overdue monitoring items", f"{self.overdue_items}", "count"),
            ("line within reach of a post", f"{self.covered_share:.1%}", "line length"),
            ("longest blind stretch", f"{self.longest_gap_m:.0f} m", "line length"),
            ("open findings", f"{self.open_findings}", "count"),
            ("overdue findings", f"{self.overdue_findings}", "count"),
            ("pipe under a finding", f"{self.finding_length_m:.0f} m", "line length"),
        ]

    def render(self) -> str:
        """The whole slide."""
        table = Table(
            columns=KPI_COLUMNS,
            title=f"Programme, {self.line_code}, as at {self.as_of.isoformat()}",
        )
        for figure, value, over in self.rows():
            table.add(figure=figure, value=value, over=over)
        return table.render()


def build_kpis(
    assessment: LineAssessment,
    register: list[DueItem],
    coverage_report: CoverageReport,
    findings: list[Finding],
) -> Kpis:
    """Pull one line's figures together."""
    longest = coverage_report.longest_gap
    open_findings = [item for item in findings if item.is_open]
    return Kpis(
        line_code=assessment.line.code,
        as_of=assessment.as_of,
        posts=len(assessment.posts),
        judged_posts=len(assessment.assessed),
        protected_posts=len(assessment.protected),
        never_read_posts=len(assessment.unread),
        stale_posts=len(assessment.stale),
        protection_rate=assessment.protection_rate,
        compliance_rate=compliance_rate(register),
        overdue_items=len(overdue(register)),
        covered_share=coverage_report.covered_share,
        longest_gap_m=0.0 if longest is None else longest.length_m,
        open_findings=len(open_findings),
        overdue_findings=sum(1 for item in open_findings if item.is_overdue(assessment.as_of)),
        finding_length_m=sum(item.length_m for item in open_findings),
    )
