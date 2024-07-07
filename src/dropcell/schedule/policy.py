"""Monitoring policy, which is two rules that measure each other.

Every monitoring obligation in this trade is written the same way and the shape
of it catches people out every time. A rectifier is read six times a calendar
year, at intervals not exceeding two and a half months. A test post is read once
a calendar year, at intervals not exceeding fifteen months.

Those are not one rule stated twice. They are two rules that constrain
different things, and a programme can satisfy either one on its own while
failing the other.

Six readings taken in the last week of December satisfy the count and break the
interval by nine months. One reading every fourteen months satisfies the
interval forever and misses a calendar year entirely, because a year with no
reading in it is a year the count was zero however tidy the spacing looked.

So the count is evaluated per calendar year, over completed years only, and the
interval is evaluated over consecutive pairs, across year boundaries. Nothing
about one of them can be worked out from the other, and a policy that carries
only one of the two numbers is a policy with a hole in it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import PolicyError

MAX_SENSIBLE_INTERVAL_DAYS = 731


class AssetKind(StrEnum):
    """What sort of thing a rule applies to."""

    TEST_POINT = "test_point"
    RECTIFIER = "rectifier"
    CRITICAL_BOND = "critical_bond"
    ORDINARY_BOND = "ordinary_bond"
    CASING = "casing"
    CROSSING = "crossing"
    ISOLATION_JOINT = "isolation_joint"


@dataclass(frozen=True)
class MonitoringRule:
    """One obligation, carrying both of its halves."""

    key: str
    asset_kind: AssetKind
    times_per_calendar_year: int
    maximum_interval_days: int
    label: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise PolicyError("a rule needs a key")
        if self.times_per_calendar_year < 1:
            raise PolicyError(
                "a rule that requires nothing per year is not a rule",
                key=self.key,
                times=self.times_per_calendar_year,
            )
        if self.maximum_interval_days < 1:
            raise PolicyError(
                "the maximum interval has to be at least a day",
                key=self.key,
                days=self.maximum_interval_days,
            )
        if self.maximum_interval_days > MAX_SENSIBLE_INTERVAL_DAYS:
            raise PolicyError(
                "an interval over two years leaves a whole calendar year with nothing in it",
                key=self.key,
                days=self.maximum_interval_days,
                limit=MAX_SENSIBLE_INTERVAL_DAYS,
            )

    @property
    def nominal_interval_days(self) -> float:
        """The spacing the count implies on its own, ignoring the interval rule."""
        return 365.25 / self.times_per_calendar_year

    @property
    def interval_is_binding(self) -> bool:
        """Whether the interval rule bites before the count rule does.

        With six readings a year the count implies about sixty one days and the
        interval allows seventy five, so the count is what drives the schedule.
        With one reading a year the count implies a year and the interval allows
        fifteen months, so the count drives it again. The interval only takes
        over where somebody has written a policy tighter than the count.
        """
        return self.maximum_interval_days < self.nominal_interval_days

    def next_due(self, last_done: dt.date) -> dt.date:
        """The last day a following visit can happen without breaking the interval."""
        return last_done + dt.timedelta(days=self.maximum_interval_days)


@dataclass(frozen=True)
class MonitoringPolicy:
    """The set of rules an operator works to."""

    name: str
    rules: tuple[MonitoringRule, ...]
    effective_from: dt.date

    def __post_init__(self) -> None:
        if not self.rules:
            raise PolicyError("a policy with no rules covers nothing", name=self.name)
        seen: set[str] = set()
        for rule in self.rules:
            if rule.key in seen:
                raise PolicyError("two rules share a key", name=self.name, key=rule.key)
            seen.add(rule.key)

    def rule(self, key: str) -> MonitoringRule:
        """One rule by key."""
        for candidate in self.rules:
            if candidate.key == key:
                return candidate
        raise PolicyError(
            "no rule by that key",
            name=self.name,
            key=key,
            known=sorted(item.key for item in self.rules),
        )

    def for_asset(self, kind: AssetKind) -> tuple[MonitoringRule, ...]:
        """Every rule that applies to one sort of thing."""
        return tuple(rule for rule in self.rules if rule.asset_kind is kind)

    def covers(self, on: dt.date) -> bool:
        """Whether this policy was in force on a date."""
        return on >= self.effective_from


TEST_POINT_ANNUAL = MonitoringRule(
    key="test_point_annual",
    asset_kind=AssetKind.TEST_POINT,
    times_per_calendar_year=1,
    maximum_interval_days=456,
    label="once a calendar year, at intervals not over fifteen months",
)

RECTIFIER_BIMONTHLY = MonitoringRule(
    key="rectifier_bimonthly",
    asset_kind=AssetKind.RECTIFIER,
    times_per_calendar_year=6,
    maximum_interval_days=75,
    label="six times a calendar year, at intervals not over two and a half months",
)

CRITICAL_BOND_BIMONTHLY = MonitoringRule(
    key="critical_bond_bimonthly",
    asset_kind=AssetKind.CRITICAL_BOND,
    times_per_calendar_year=6,
    maximum_interval_days=75,
    label="on the rectifier cycle, because protection depends on it",
)

CASING_ANNUAL = MonitoringRule(
    key="casing_annual",
    asset_kind=AssetKind.CASING,
    times_per_calendar_year=1,
    maximum_interval_days=456,
    label="once a calendar year with the test posts",
)

ISOLATION_ANNUAL = MonitoringRule(
    key="isolation_annual",
    asset_kind=AssetKind.ISOLATION_JOINT,
    times_per_calendar_year=1,
    maximum_interval_days=456,
    label="once a calendar year with the test posts",
)

STANDARD_POLICY = MonitoringPolicy(
    name="standard",
    rules=(
        TEST_POINT_ANNUAL,
        RECTIFIER_BIMONTHLY,
        CRITICAL_BOND_BIMONTHLY,
        CASING_ANNUAL,
        ISOLATION_ANNUAL,
    ),
    effective_from=dt.date(2000, 1, 1),
)
