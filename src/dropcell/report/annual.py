"""The annual document, which is the one that has to survive being read in five years.

Everything else here answers a question somebody asked this morning. This is the
record of what the programme did in a year, and it will be read by somebody who
was not there, probably after an incident, looking for what was known and when.

So it says what was not done as loudly as what was. A year's report that lists
four hundred readings and does not mention the eleven posts nobody could get to
is a report that will be quoted back at whoever signed it.

It carries the thresholds it was produced under. Criteria move between
standards and between operators, and a figure of ninety four percent protected
means nothing five years later unless the page says what it was measured
against.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.analysis.line import LineAssessment
from dropcell.config import Settings
from dropcell.findings.finding import Finding
from dropcell.report.exceptions import summarise as summarise_exceptions
from dropcell.report.protection import summarise as summarise_protection
from dropcell.schedule.register import DueItem, compliance_rate, overdue
from dropcell.store.imports import ImportRun


@dataclass(frozen=True)
class AnnualReport:
    """One year of a programme on one line."""

    year: int
    assessment: LineAssessment
    register: tuple[DueItem, ...]
    findings: tuple[Finding, ...]
    imports: tuple[ImportRun, ...]
    settings: Settings
    prepared_on: dt.date
    prepared_by: str = ""

    @property
    def raised_this_year(self) -> tuple[Finding, ...]:
        """Findings raised inside the year being reported."""
        return tuple(item for item in self.findings if item.raised_on.year == self.year)

    @property
    def closed_this_year(self) -> tuple[Finding, ...]:
        """Findings closed inside the year being reported."""
        return tuple(
            item
            for item in self.findings
            if item.closed_on is not None and item.closed_on.year == self.year
        )

    @property
    def carried_forward(self) -> tuple[Finding, ...]:
        """Findings still open at the end of the year."""
        return tuple(item for item in self.findings if item.is_open)

    @property
    def imports_this_year(self) -> tuple[ImportRun, ...]:
        """Files loaded inside the year being reported."""
        return tuple(item for item in self.imports if item.imported_at.year == self.year)

    def thresholds(self) -> list[tuple[str, str]]:
        """What the figures on this page were measured against."""
        return [
            ("protection criterion", f"{self.settings.protection_mv:.0f} mV instant off"),
            ("decay criterion", f"{self.settings.decay_mv:.0f} mV"),
            ("over protection limit", f"{self.settings.over_protection_mv:.0f} mV"),
            (
                "AC bands",
                f"{self.settings.ac_low_risk_a_per_m2:.0f} and "
                f"{self.settings.ac_high_risk_a_per_m2:.0f} A per square metre",
            ),
            ("post reach", f"{self.settings.post_reach_m:.0f} m"),
        ]

    def not_done(self) -> list[str]:
        """Everything the year did not manage, stated plainly."""
        said: list[str] = []
        unread = self.assessment.unread
        if unread:
            codes = ", ".join(item.code for item in unread)
            said.append(f"{len(unread)} posts were not read at all: {codes}")
        stale = self.assessment.stale
        if stale:
            said.append(
                f"{len(stale)} posts were last read over fifteen months before the year end"
            )
        off_segment = self.assessment.off_segment
        if off_segment:
            said.append(
                f"{len(off_segment)} posts sit on pipe no segment describes"
                " and could not be judged"
            )
        late = overdue(list(self.register))
        if late:
            said.append(f"{len(late)} monitoring obligations were overdue at the year end")
        carried = self.carried_forward
        if carried:
            said.append(f"{len(carried)} findings were carried into the following year")
        if not said:
            said.append("nothing was left undone")
        return said

    def render(self) -> str:
        """The whole document."""
        line = self.assessment.line
        protection = summarise_protection(self.assessment)
        exceptions = summarise_exceptions(list(self.findings), self.assessment.as_of)
        lines = [
            f"Cathodic protection, annual report {self.year}",
            f"{line.code}  {line.name}",
            f"operator {line.operator}, {line.length_m:.0f} m of {line.commodity}",
            f"prepared {self.prepared_on.isoformat()}"
            + (f" by {self.prepared_by}" if self.prepared_by else ""),
            "",
            "Measured against",
            "",
        ]
        lines.extend(f"  {name:<24} {value}" for name, value in self.thresholds())
        lines.extend(
            [
                "",
                "Monitoring",
                "",
                f"  {len(self.imports_this_year)} survey files loaded",
                f"  {protection.posts} posts on the line, {protection.judged} judged",
                f"  {protection.protected} met a criterion, "
                f"{protection.under_criterion} did not",
                f"  protection rate {protection.rate:.1%} of judged posts",
                f"  monitoring compliance {compliance_rate(list(self.register)):.1%}"
                " of asset and rule pairs",
                "",
                "Exceptions",
                "",
                f"  {len(self.raised_this_year)} raised in the year",
                f"  {len(self.closed_this_year)} closed in the year",
                f"  {len(self.carried_forward)} carried forward",
                f"  {exceptions.overdue} overdue at the year end",
                f"  {exceptions.total_length_m:.0f} m of pipe under a finding",
                "",
                "What was not done",
                "",
            ]
        )
        lines.extend(f"  {item}" for item in self.not_done())
        return "\n".join(lines)
