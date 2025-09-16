"""One place that gathers everything about a line.

Four commands were each assembling the same six things in the same order:
fetch the line, its segments, its posts, assess it, build its monitoring
register, and pull its findings. Written out four times they had drifted. Two of
them passed the settings into the assessment and two did not, so the same line
reported one criterion on the programme page and a different one on the annual
document, and nothing said so.

Gathering it once is worth more than the lines it saves. The order matters,
because assessing a line with no posts raises rather than returning an empty
assessment, and every one of these has to decide what to do about that. Deciding
it once means every page decides it the same way.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.analysis.coverage import CoverageReport, coverage
from dropcell.analysis.line import LineAssessment, assess_line
from dropcell.analysis.schedule import line_histories
from dropcell.config import Settings
from dropcell.errors import NotFoundError
from dropcell.findings.finding import Finding
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.schedule.policy import STANDARD_POLICY, MonitoringPolicy
from dropcell.schedule.register import DueItem, build_register, overdue
from dropcell.store.database import Database
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository


@dataclass(frozen=True)
class LineView:
    """Everything one page needs about one line, gathered once."""

    line: Line
    as_of: dt.date
    segments: tuple[Segment, ...]
    posts: tuple[TestPoint, ...]
    assessment: LineAssessment | None
    register: tuple[DueItem, ...]
    findings: tuple[Finding, ...]
    coverage: CoverageReport

    @property
    def has_posts(self) -> bool:
        """Whether there is anything on this line to read."""
        return bool(self.posts)

    @property
    def judged(self) -> int:
        """How many posts a criterion could be applied to."""
        return 0 if self.assessment is None else len(self.assessment.assessed)

    @property
    def protected(self) -> int:
        """How many met one."""
        return 0 if self.assessment is None else len(self.assessment.protected)

    @property
    def unread(self) -> int:
        """How many nobody has read."""
        return 0 if self.assessment is None else len(self.assessment.unread)

    @property
    def protection_rate(self) -> float:
        """The share of judged posts that met a criterion."""
        return 0.0 if self.assessment is None else self.assessment.protection_rate

    @property
    def overdue(self) -> tuple[DueItem, ...]:
        """Everything on the monitoring register that is late."""
        return tuple(overdue(list(self.register)))

    @property
    def open_findings(self) -> tuple[Finding, ...]:
        """Everything still on the exception register."""
        return tuple(item for item in self.findings if item.is_open)


def gather(
    database: Database,
    line_code: str,
    *,
    as_of: dt.date,
    settings: Settings | None = None,
    policy: MonitoringPolicy = STANDARD_POLICY,
) -> LineView:
    """Fetch everything about one line, in the order that works.

    A line with no posts gets no assessment rather than an exception. That is
    not the same as a line whose posts all failed and it is not the same as an
    error, and a page that cannot tell those apart is a page that reports a
    line nobody has built as a line in trouble.
    """
    figures = settings or Settings()
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    posts = TestPointRepository(database).for_line(line.code)
    assessment: LineAssessment | None = None
    if posts:
        try:
            assessment = assess_line(database, line.code, as_of=as_of, settings=figures)
        except NotFoundError:
            assessment = None
    return LineView(
        line=line,
        as_of=as_of,
        segments=tuple(segments),
        posts=tuple(posts),
        assessment=assessment,
        register=tuple(
            build_register(
                policy,
                line_histories(database, line.code, until=as_of),
                as_of=as_of,
            )
        ),
        findings=tuple(FindingRepository(database).for_line(line.code)),
        coverage=coverage(line, segments, posts, reach_m=figures.post_reach_m),
    )
