"""How much of the line anybody can actually see.

A protection rate of a hundred percent means every post that was read met a
criterion. It says nothing about the pipe between the posts, and on a line with
one post every two miles that is nearly all of the pipe. A programme can be
fully compliant, fully protected on paper, and blind over ninety nine percent of
its length.

So the second question after how the posts read is how far apart they are, and
which stretches have nothing on them at all. A segment with no post is not a
segment that is failing. It is a segment nobody has any evidence about, and the
two get confused constantly because both of them produce no findings.

Shielding coatings make this sharper rather than softer. Where the coating can
shield, a post is evidence about the post and nothing else, so the stretch
either side of it is unmonitored no matter how close the next one is.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station, StationRange

DEFAULT_REACH_M = 1600.0


@dataclass(frozen=True)
class Gap:
    """A stretch of line with no post close enough to speak for it."""

    extent: StationRange
    before: str | None
    after: str | None

    @property
    def length_m(self) -> float:
        """How much pipe the gap covers."""
        return self.extent.length_m

    @property
    def at_an_end(self) -> bool:
        """Whether the gap runs off one end of the line."""
        return self.before is None or self.after is None


@dataclass(frozen=True)
class CoverageReport:
    """What the posts on one line can and cannot see."""

    line_code: str
    length_m: float
    posts: int
    reach_m: float
    gaps: tuple[Gap, ...]
    segments_without_posts: tuple[str, ...]

    @property
    def uncovered_m(self) -> float:
        """How much pipe no post speaks for."""
        return sum(gap.length_m for gap in self.gaps)

    @property
    def covered_m(self) -> float:
        """How much pipe a post does speak for."""
        return max(0.0, self.length_m - self.uncovered_m)

    @property
    def covered_share(self) -> float:
        """The share of the line inside reach of a post."""
        if self.length_m <= 0:
            return 0.0
        return self.covered_m / self.length_m

    @property
    def longest_gap(self) -> Gap | None:
        """The worst single blind stretch."""
        return max(self.gaps, key=lambda gap: gap.length_m) if self.gaps else None

    @property
    def mean_spacing_m(self) -> float | None:
        """Average distance between posts, which is the number people quote."""
        if self.posts < 2:
            return None
        return self.length_m / (self.posts - 1)


def find_gaps(
    line: Line,
    posts: list[TestPoint],
    *,
    reach_m: float = DEFAULT_REACH_M,
) -> list[Gap]:
    """Stretches of line further than the reach from any post."""
    if reach_m <= 0:
        raise ValidationError("a post has to speak for some length", reach_m=reach_m)
    ordered = sorted(posts, key=lambda post: post.station.metres)
    gaps: list[Gap] = []
    cursor = 0.0
    previous: str | None = None
    for post in ordered:
        covered_from = post.station.metres - reach_m
        if covered_from > cursor:
            gaps.append(
                Gap(
                    extent=StationRange(Station(cursor), Station(covered_from)),
                    before=previous,
                    after=post.code,
                )
            )
        cursor = max(cursor, post.station.metres + reach_m)
        previous = post.code
    if cursor < line.length_m:
        gaps.append(
            Gap(
                extent=StationRange(Station(cursor), Station(line.length_m)),
                before=previous,
                after=None,
            )
        )
    return gaps


def segments_without_posts(segments: list[Segment], posts: list[TestPoint]) -> list[str]:
    """Segments with no post standing on them at all."""
    stations = [post.station for post in posts]
    return [
        segment.code
        for segment in segments
        if not any(segment.contains(station) for station in stations)
    ]


def coverage(
    line: Line,
    segments: list[Segment],
    posts: list[TestPoint],
    *,
    reach_m: float = DEFAULT_REACH_M,
) -> CoverageReport:
    """Work out what the posts on one line can see."""
    return CoverageReport(
        line_code=line.code,
        length_m=line.length_m,
        posts=len(posts),
        reach_m=reach_m,
        gaps=tuple(find_gaps(line, posts, reach_m=reach_m)),
        segments_without_posts=tuple(segments_without_posts(segments, posts)),
    )


def shielded_reach(segment: Segment, reach_m: float = DEFAULT_REACH_M) -> float:
    """The reach a post has on this segment, which a shielding coating collapses."""
    return 0.0 if segment.needs_above_ground_survey else reach_m
