"""Watching a post drift, which is the finding a single reading cannot make.

A post reading minus nine hundred and ten this year and minus nine hundred and
five last year has passed both times and will pass next year. A post that has
gone from minus one thousand and fifty to minus nine hundred and ten over six
years has not failed anything yet and is going to, and the year it does is
worth knowing now rather than then.

The fit is an ordinary least squares line through the readings against time.
That is a crude model of something that is not linear, and it is used anyway,
because the alternative is a model with parameters nobody can defend and the
question being asked is only ever which way and roughly how fast.

Two things it will not do. It will not extrapolate from two readings, because a
line through two points has no residual and therefore no way to say whether it
means anything. And it will not report a crossing date beyond the horizon it
was given, because a slope of a millivolt a year says the pipe fails in eighty
years and that is not a prediction, it is arithmetic on noise.
"""

from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass

from dropcell.criteria.potential import DEFAULT_PROTECTION_MV
from dropcell.errors import ValidationError
from dropcell.model.reading import Reading

DAYS_PER_YEAR = 365.25
MINIMUM_READINGS = 3
DEFAULT_HORIZON_YEARS = 20.0


@dataclass(frozen=True)
class Trend:
    """A straight line through one post's history."""

    test_point_code: str
    readings: int
    first_on: dt.date
    last_on: dt.date
    slope_mv_per_year: float
    intercept_mv: float
    residual_mv: float
    latest_mv: float

    @property
    def span_years(self) -> float:
        """How long the history covers."""
        return (self.last_on - self.first_on).days / DAYS_PER_YEAR

    @property
    def drifting_positive(self) -> bool:
        """Whether the pipe is getting less protected as time goes on."""
        return self.slope_mv_per_year > 0

    def value_at(self, when: dt.date) -> float:
        """What the fitted line says the potential is on a date."""
        years = (when - self.first_on).days / DAYS_PER_YEAR
        return self.intercept_mv + self.slope_mv_per_year * years

    def crosses(
        self,
        threshold_mv: float = DEFAULT_PROTECTION_MV,
        *,
        horizon_years: float = DEFAULT_HORIZON_YEARS,
    ) -> dt.date | None:
        """When the fitted line reaches a threshold, if it does so in the horizon."""
        if horizon_years <= 0:
            raise ValidationError("a horizon has to run forwards", years=horizon_years)
        if self.slope_mv_per_year <= 0:
            return None
        years_from_start = (threshold_mv - self.intercept_mv) / self.slope_mv_per_year
        crossing = self.first_on + dt.timedelta(days=years_from_start * DAYS_PER_YEAR)
        if crossing < self.last_on:
            return self.last_on
        if (crossing - self.last_on).days > horizon_years * DAYS_PER_YEAR:
            return None
        return crossing


def fit_trend(
    test_point_code: str,
    readings: list[Reading],
    *,
    use_off: bool = True,
) -> Trend | None:
    """Fit a line through a post's history, or nothing if there is too little of it."""
    points: list[tuple[float, float]] = []
    ordered = sorted(readings, key=lambda reading: reading.taken_on)
    if not ordered:
        return None
    origin = ordered[0].taken_on
    for reading in ordered:
        value = reading.off_cse_mv if use_off else reading.on_cse_mv
        if value is None:
            continue
        years = (reading.taken_on - origin).days / DAYS_PER_YEAR
        points.append((years, value))
    if len(points) < MINIMUM_READINGS:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    if len(set(xs)) < 2:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in points)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    residual = statistics.fmean(abs(y - (intercept + slope * x)) for x, y in points)
    return Trend(
        test_point_code=test_point_code,
        readings=len(points),
        first_on=origin,
        last_on=ordered[-1].taken_on,
        slope_mv_per_year=slope,
        intercept_mv=intercept,
        residual_mv=residual,
        latest_mv=ys[-1],
    )


def worst_drift_first(trends: list[Trend]) -> list[Trend]:
    """Order posts by how fast they are losing protection."""
    return sorted(
        trends,
        key=lambda trend: (-trend.slope_mv_per_year, trend.test_point_code),
    )


def crossing_within(
    trends: list[Trend],
    years: float,
    *,
    threshold_mv: float = DEFAULT_PROTECTION_MV,
) -> list[Trend]:
    """Posts whose fitted line reaches the threshold inside a planning horizon."""
    return [
        trend
        for trend in trends
        if trend.crosses(threshold_mv, horizon_years=years) is not None
    ]
