"""Close interval surveys, which are the only way to see between the posts.

A test post every mile tells you about a few square inches of pipe a mile
apart. A close interval survey walks the whole line with the rectifiers being
interrupted on a timer, dropping the cell every few paces and taking an on and
an off reading at each step. What comes back is a profile rather than a set of
points, and the questions asked of it are about stretches: where does the line
fall under criterion, for how far, and by how much.

The data is messy in specific ways. Contact between the cell and the soil is
sometimes poor, which puts a spike into both traces at once. The crew skips
ground they cannot reach, which leaves gaps that are not the same thing as
missing protection. Both of those have to be recognised before any length is
added up, or the report ends up counting a farmyard as a corrosion problem.
"""

from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass, field

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.model.testpoint import check_potential
from dropcell.stationing import Station, StationRange

DEFAULT_INTERVAL_M = 1.5
GAP_MULTIPLE = 3.0


@dataclass(frozen=True)
class CisPoint:
    """One step along the line."""

    station: Station
    on_mv: float
    off_mv: float | None = None
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        check_potential(self.on_mv, "on potential")
        if self.off_mv is not None:
            check_potential(self.off_mv, "off potential")

    @property
    def ir_drop_mv(self) -> float | None:
        """How much of the on reading was soil."""
        if self.off_mv is None:
            return None
        return self.on_mv - self.off_mv

    @property
    def has_off(self) -> bool:
        """Whether the interrupter was working at this step."""
        return self.off_mv is not None


@dataclass(frozen=True)
class CisSurvey:
    """One walk of one stretch of line."""

    line_code: str
    taken_on: dt.date
    points: tuple[CisPoint, ...]
    nominal_interval_m: float = DEFAULT_INTERVAL_M
    technician: str = ""
    direction: str = "upstream"

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if len(self.points) < 2:
            raise ValidationError(
                "a close interval survey needs more than one step",
                line_code=self.line_code,
                count=len(self.points),
            )
        if self.nominal_interval_m <= 0:
            raise ValidationError(
                "the nominal interval must be positive",
                line_code=self.line_code,
                interval_m=self.nominal_interval_m,
            )
        ordered = tuple(sorted(self.points, key=lambda point: point.station.metres))
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            if earlier.station.metres == later.station.metres:
                raise ValidationError(
                    "two readings at the same station",
                    line_code=self.line_code,
                    station_m=earlier.station.metres,
                )
        object.__setattr__(self, "points", ordered)

    @property
    def extent(self) -> StationRange:
        """The stretch of line the survey covers."""
        return StationRange(self.points[0].station, self.points[-1].station)

    @property
    def length_m(self) -> float:
        """How much line the survey walked."""
        return self.extent.length_m

    @property
    def interrupted_points(self) -> tuple[CisPoint, ...]:
        """Only the steps that caught an off reading."""
        return tuple(point for point in self.points if point.has_off)

    @property
    def interruption_coverage(self) -> float:
        """The share of steps that caught an off reading."""
        return len(self.interrupted_points) / len(self.points)

    @property
    def mean_off_mv(self) -> float | None:
        """Average polarised potential over the walk."""
        values = [point.off_mv for point in self.interrupted_points if point.off_mv is not None]
        return statistics.fmean(values) if values else None

    @property
    def most_positive_off_mv(self) -> float | None:
        """The least protected step in the whole survey."""
        values = [point.off_mv for point in self.interrupted_points if point.off_mv is not None]
        return max(values) if values else None

    @property
    def most_negative_off_mv(self) -> float | None:
        """The most protected step in the whole survey."""
        values = [point.off_mv for point in self.interrupted_points if point.off_mv is not None]
        return min(values) if values else None

    def spacings_m(self) -> list[float]:
        """The distance between each pair of consecutive steps."""
        return [
            later.station.metres - earlier.station.metres
            for earlier, later in zip(self.points, self.points[1:], strict=False)
        ]

    def gaps(self, *, multiple: float = GAP_MULTIPLE) -> list[StationRange]:
        """Stretches the crew stepped over rather than walked.

        A step longer than a few times the nominal interval is ground somebody
        could not get onto. It is not a reading and it is not evidence of
        anything, so it has to be excluded from a length before the length means
        what a reader will take it to mean.
        """
        if multiple <= 1:
            raise ValidationError(
                "a gap has to be wider than the nominal step", multiple=multiple
            )
        limit = self.nominal_interval_m * multiple
        found: list[StationRange] = []
        for earlier, later in zip(self.points, self.points[1:], strict=False):
            if later.station.metres - earlier.station.metres > limit:
                found.append(StationRange(earlier.station, later.station))
        return found

    def points_in(self, extent: StationRange) -> tuple[CisPoint, ...]:
        """Every step inside a stretch of line."""
        return tuple(point for point in self.points if extent.contains(point.station))

    def nearest(self, station: Station) -> CisPoint:
        """The step closest to a station, which is how a post is tied to the trace."""
        return min(self.points, key=lambda point: abs(point.station.metres - station.metres))
