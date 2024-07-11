"""Reading a visit history against a rule that has two halves.

The count half is judged over completed calendar years only. The year in
progress cannot be short yet, because there is still time left in it to do the
work, and reporting a live year as a failure every January is how a compliance
report gets ignored.

The interval half is judged over consecutive pairs, and it does not stop at the
end of the year. A visit in November and the next one in the following March is
one interval of a hundred and twenty days regardless of the fact that a year
boundary sits inside it.

There are two more intervals that are easy to miss and one of them is usually
the one that matters. The gap between the last visit and today is an interval
too. It has no closing visit yet, so it does not appear in any pairing of the
history, and an asset that has quietly not been read for two years shows a
clean pair list and a clean year count for as long as the current year is still
running. The gap from the day an asset went into service to its first visit is
the same problem at the other end.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.schedule.policy import MonitoringRule


@dataclass(frozen=True)
class YearCount:
    """How many visits one completed calendar year got."""

    year: int
    visits: int
    required: int

    @property
    def met(self) -> bool:
        """Whether the year had enough visits in it."""
        return self.visits >= self.required

    @property
    def short_by(self) -> int:
        """How many visits the year was missing."""
        return max(0, self.required - self.visits)


@dataclass(frozen=True)
class IntervalBreach:
    """One gap between visits that ran longer than the rule allows."""

    previous: dt.date
    following: dt.date | None
    days: int
    limit_days: int

    @property
    def over_by_days(self) -> int:
        """How far past the limit the gap ran."""
        return self.days - self.limit_days

    @property
    def still_open(self) -> bool:
        """Whether the gap has no closing visit yet."""
        return self.following is None


@dataclass(frozen=True)
class ComplianceResult:
    """What one rule says about one asset's history."""

    asset_code: str
    rule_key: str
    visits: tuple[dt.date, ...]
    year_counts: tuple[YearCount, ...]
    breaches: tuple[IntervalBreach, ...]
    next_due: dt.date | None
    as_of: dt.date

    @property
    def short_years(self) -> tuple[YearCount, ...]:
        """Completed years that did not get enough visits."""
        return tuple(year for year in self.year_counts if not year.met)

    @property
    def open_breach(self) -> IntervalBreach | None:
        """The gap that is still running, if it has already gone too long."""
        for breach in self.breaches:
            if breach.still_open:
                return breach
        return None

    @property
    def compliant(self) -> bool:
        """Whether both halves of the rule were satisfied."""
        return not self.short_years and not self.breaches

    @property
    def overdue(self) -> bool:
        """Whether the asset is past its next due date right now."""
        return self.next_due is not None and self.as_of > self.next_due

    @property
    def days_until_due(self) -> int | None:
        """How long there is before the next visit has to happen."""
        if self.next_due is None:
            return None
        return (self.next_due - self.as_of).days

    def reasons(self) -> tuple[str, ...]:
        """Plain sentences a report can print for each half that failed."""
        said: list[str] = []
        for year in self.short_years:
            said.append(f"{year.year} got {year.visits} of {year.required} required visits")
        for breach in self.breaches:
            if breach.still_open:
                said.append(
                    f"nothing since {breach.previous.isoformat()}, "
                    f"{breach.days} days against a limit of {breach.limit_days}"
                )
            else:
                assert breach.following is not None
                said.append(
                    f"{breach.previous.isoformat()} to {breach.following.isoformat()} "
                    f"is {breach.days} days against a limit of {breach.limit_days}"
                )
        return tuple(said)


def evaluate_rule(
    rule: MonitoringRule,
    visits: list[dt.date],
    *,
    asset_code: str,
    as_of: dt.date,
    in_service_from: dt.date | None = None,
) -> ComplianceResult:
    """Judge one asset's visit history against one rule."""
    ordered = sorted(set(visits))
    if any(visit > as_of for visit in ordered):
        raise ValidationError(
            "a visit cannot be in the future",
            asset_code=asset_code,
            as_of=as_of.isoformat(),
        )
    anchor = in_service_from or (ordered[0] if ordered else None)
    year_counts = _count_years(rule, ordered, anchor, as_of)
    breaches = _find_breaches(rule, ordered, anchor, as_of)
    last = ordered[-1] if ordered else anchor
    next_due = None if last is None else rule.next_due(last)
    return ComplianceResult(
        asset_code=asset_code,
        rule_key=rule.key,
        visits=tuple(ordered),
        year_counts=year_counts,
        breaches=breaches,
        next_due=next_due,
        as_of=as_of,
    )


def _count_years(
    rule: MonitoringRule,
    visits: list[dt.date],
    anchor: dt.date | None,
    as_of: dt.date,
) -> tuple[YearCount, ...]:
    if anchor is None:
        return ()
    counts: list[YearCount] = []
    for year in range(anchor.year, as_of.year):
        in_year = sum(1 for visit in visits if visit.year == year)
        counts.append(
            YearCount(year=year, visits=in_year, required=rule.times_per_calendar_year)
        )
    return tuple(counts)


def _find_breaches(
    rule: MonitoringRule,
    visits: list[dt.date],
    anchor: dt.date | None,
    as_of: dt.date,
) -> tuple[IntervalBreach, ...]:
    found: list[IntervalBreach] = []
    points = list(visits)
    if anchor is not None and (not points or anchor < points[0]):
        points.insert(0, anchor)
    for earlier, later in zip(points, points[1:], strict=False):
        days = (later - earlier).days
        if days > rule.maximum_interval_days:
            found.append(
                IntervalBreach(
                    previous=earlier,
                    following=later,
                    days=days,
                    limit_days=rule.maximum_interval_days,
                )
            )
    tail = points[-1] if points else None
    if tail is not None:
        open_days = (as_of - tail).days
        if open_days > rule.maximum_interval_days:
            found.append(
                IntervalBreach(
                    previous=tail,
                    following=None,
                    days=open_days,
                    limit_days=rule.maximum_interval_days,
                )
            )
    return tuple(found)
