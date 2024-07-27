"""The due register, which is the whole programme on one page.

One asset against one rule is a compliance result. A hundred rectifiers and
four hundred posts against the policy is a work plan, and the questions asked of
it are not the same. Nobody wants to know whether post one one four is
compliant. They want to know what has to be done this month, what is already
late, and how much of the year's work is still in front of them.

Ordering is the part worth getting right. Late work is not simply work with a
date in the past: an asset that is a week over its interval and one that has not
been touched since the last policy are both overdue, and putting them in the
same undifferentiated list is how the second one stays that way. So the register
sorts by how far past due a thing is, and an asset that has never been visited
sorts above everything with a history.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.schedule.compliance import ComplianceResult, evaluate_rule
from dropcell.schedule.policy import AssetKind, MonitoringPolicy


@dataclass(frozen=True)
class AssetHistory:
    """One thing that has to be visited, and when it has been."""

    code: str
    kind: AssetKind
    visits: tuple[dt.date, ...] = ()
    in_service_from: dt.date | None = None

    @property
    def ever_visited(self) -> bool:
        """Whether anybody has been to it at all."""
        return bool(self.visits)


@dataclass(frozen=True)
class DueItem:
    """One asset against one rule, reduced to what a planner needs."""

    asset_code: str
    asset_kind: AssetKind
    rule_key: str
    next_due: dt.date | None
    days_until_due: int | None
    overdue: bool
    compliant: bool
    ever_visited: bool
    result: ComplianceResult

    @property
    def days_overdue(self) -> int:
        """How far past due it is, or nothing when it is not."""
        if self.days_until_due is None or self.days_until_due >= 0:
            return 0
        return -self.days_until_due

    @property
    def sort_key(self) -> tuple[int, int, str]:
        """Never visited first, then most overdue, then by code."""
        return (0 if not self.ever_visited else 1, -self.days_overdue, self.asset_code)


def build_register(
    policy: MonitoringPolicy,
    histories: Iterable[AssetHistory],
    *,
    as_of: dt.date,
) -> list[DueItem]:
    """Run every rule that applies to every asset and sort what comes out."""
    if not policy.covers(as_of):
        raise ValidationError(
            "the policy was not in force on that date",
            policy=policy.name,
            as_of=as_of.isoformat(),
            effective_from=policy.effective_from.isoformat(),
        )
    items: list[DueItem] = []
    for history in histories:
        for rule in policy.for_asset(history.kind):
            result = evaluate_rule(
                rule,
                list(history.visits),
                asset_code=history.code,
                as_of=as_of,
                in_service_from=history.in_service_from,
            )
            items.append(
                DueItem(
                    asset_code=history.code,
                    asset_kind=history.kind,
                    rule_key=rule.key,
                    next_due=result.next_due,
                    days_until_due=result.days_until_due,
                    overdue=result.overdue,
                    compliant=result.compliant,
                    ever_visited=history.ever_visited,
                    result=result,
                )
            )
    return sorted(items, key=lambda item: item.sort_key)


def overdue(register: list[DueItem]) -> list[DueItem]:
    """Only the work that is already late."""
    return [item for item in register if item.overdue or not item.ever_visited]


def due_within(register: list[DueItem], days: int, *, as_of: dt.date) -> list[DueItem]:
    """Work that falls due inside a window, late work included."""
    if days < 0:
        raise ValidationError("a window cannot run backwards", days=days)
    horizon = as_of + dt.timedelta(days=days)
    found: list[DueItem] = []
    for item in register:
        if item.next_due is None:
            found.append(item)
            continue
        if item.next_due <= horizon:
            found.append(item)
    return found


def by_month(register: list[DueItem]) -> dict[tuple[int, int], list[DueItem]]:
    """The register grouped into the months the work falls in."""
    grouped: dict[tuple[int, int], list[DueItem]] = {}
    for item in register:
        if item.next_due is None:
            continue
        key = (item.next_due.year, item.next_due.month)
        grouped.setdefault(key, []).append(item)
    return grouped


def compliance_rate(register: list[DueItem]) -> float:
    """The share of the register that satisfies both halves of its rule."""
    if not register:
        return 1.0
    return sum(1 for item in register if item.compliant) / len(register)
