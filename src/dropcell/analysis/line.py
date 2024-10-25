"""Judging a whole line from what is in the register.

The pieces are all here already. A post has readings, a reading sits on a
segment, a segment picks a criterion set, and a criterion set produces a
verdict. What is left is the walking, and two decisions about what to do where
the register does not line up neatly.

A post that sits on no segment is a real thing and it happens whenever
somebody extends a line and forgets to extend the segmentation. It cannot be
judged, because there is no coating and no protection method to judge it
against, and it is reported as its own kind of problem rather than folded in
with the posts that failed a criterion.

A post whose most recent reading is years old is judged on that reading, and
the age is carried alongside the verdict. Refusing to judge it would hide a bad
reading behind a scheduling problem, and judging it without saying how old it
is presents a number from three years ago as the state of the line today.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.criteria.base import Evidence
from dropcell.criteria.evaluate import PointVerdict
from dropcell.criteria.registry import select_set
from dropcell.errors import NotFoundError
from dropcell.model.enums import LeadKind
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository

STALE_AFTER_DAYS = 456


@dataclass(frozen=True)
class PostAssessment:
    """One post, its most recent reading, and what the criteria made of it."""

    post: TestPoint
    segment: Segment | None
    reading: Reading | None
    verdict: PointVerdict | None
    criterion_set: str
    as_of: dt.date

    @property
    def code(self) -> str:
        """The post's code."""
        return self.post.code

    @property
    def reading_age_days(self) -> int | None:
        """How old the reading the verdict rests on is."""
        if self.reading is None:
            return None
        return (self.as_of - self.reading.taken_on).days

    @property
    def stale(self) -> bool:
        """Whether the reading is old enough that the verdict is historical."""
        age = self.reading_age_days
        return age is not None and age > STALE_AFTER_DAYS

    @property
    def off_segment(self) -> bool:
        """Whether the post sits on pipe no segment describes."""
        return self.segment is None

    @property
    def protected(self) -> bool:
        """Whether some criterion was met here."""
        return self.verdict is not None and self.verdict.protected

    @property
    def has_findings(self) -> bool:
        """Whether this post puts anything on the exception register."""
        return self.verdict is not None and self.verdict.has_findings


@dataclass(frozen=True)
class LineAssessment:
    """What the register says about one line on one day."""

    line: Line
    as_of: dt.date
    posts: tuple[PostAssessment, ...]

    @property
    def assessed(self) -> tuple[PostAssessment, ...]:
        """Posts a criterion could actually be applied to."""
        return tuple(
            item for item in self.posts if item.verdict is not None and item.verdict.assessed
        )

    @property
    def protected(self) -> tuple[PostAssessment, ...]:
        """Posts where a criterion was met."""
        return tuple(item for item in self.posts if item.protected)

    @property
    def under_criterion(self) -> tuple[PostAssessment, ...]:
        """Posts that were judged and did not meet anything."""
        return tuple(item for item in self.assessed if not item.protected)

    @property
    def unread(self) -> tuple[PostAssessment, ...]:
        """Posts with no reading at all."""
        return tuple(item for item in self.posts if item.reading is None)

    @property
    def stale(self) -> tuple[PostAssessment, ...]:
        """Posts whose verdict rests on an old reading."""
        return tuple(item for item in self.posts if item.stale)

    @property
    def off_segment(self) -> tuple[PostAssessment, ...]:
        """Posts sitting on pipe no segment describes."""
        return tuple(item for item in self.posts if item.off_segment)

    @property
    def protection_rate(self) -> float:
        """The share of judged posts that met a criterion."""
        judged = self.assessed
        if not judged:
            return 0.0
        return len(self.protected) / len(judged)

    def summary(self) -> str:
        """One line for the top of a report."""
        return (
            f"{self.line.code}: {len(self.protected)} of {len(self.assessed)} posts protected, "
            f"{len(self.unread)} unread, {len(self.stale)} stale"
        )


def assess_line(
    database: Database,
    line_code: str,
    *,
    as_of: dt.date,
    lead: LeadKind = LeadKind.PIPE,
) -> LineAssessment:
    """Walk one line's posts and judge each on its most recent reading."""
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    posts = TestPointRepository(database).for_line(line.code)
    readings = ReadingRepository(database)
    if not posts:
        raise NotFoundError("that line has no test points on it", code=line.code)
    assessed: list[PostAssessment] = []
    for post in posts:
        segment = _segment_for(segments, post)
        reading = readings.latest_for_point(post.code, lead)
        verdict: PointVerdict | None = None
        set_name = ""
        if segment is not None:
            selection = select_set(segment)
            set_name = selection.name
            if reading is not None:
                evidence = Evidence(
                    segment=segment,
                    on_mv=reading.on_cse_mv,
                    off_mv=reading.off_cse_mv,
                    native_mv=reading.native_mv,
                    interrupted=reading.is_interrupted,
                    label=post.code,
                )
                verdict = selection.criterion_set.evaluate(evidence)
        assessed.append(
            PostAssessment(
                post=post,
                segment=segment,
                reading=reading,
                verdict=verdict,
                criterion_set=set_name,
                as_of=as_of,
            )
        )
    return LineAssessment(line=line, as_of=as_of, posts=tuple(assessed))


def _segment_for(segments: list[Segment], post: TestPoint) -> Segment | None:
    for segment in segments:
        if segment.contains(post.station):
            return segment
    return None
