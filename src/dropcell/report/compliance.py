"""The compliance report, which is the one that goes outside the company.

Two tables and a rate. The first is what is overdue now, because that is what
somebody has to act on. The second is what falls due in a window, because that
is what somebody has to plan. The rate underneath is the number that gets
quoted, and it is quoted wrongly often enough to be worth spelling out on the
page: it is the share of asset and rule pairs that satisfied both halves of
their rule, not the share of visits that happened.

Assets that have never been visited are printed with their reason rather than
a due date, because a due date computed from an in service date reads like a
scheduling decision when it is really an admission that nobody has been.
"""

from __future__ import annotations

import datetime as dt

from dropcell.report.table import Column, Table
from dropcell.schedule.register import DueItem, compliance_rate, due_within, overdue

OVERDUE_COLUMNS = (
    Column("asset", "Asset"),
    Column("kind", "Kind", width=16),
    Column("rule", "Rule", width=24),
    Column("last", "Last visit"),
    Column("due", "Due"),
    Column("late", "Late d", align="right"),
    Column("why", "Why", width=46),
)

UPCOMING_COLUMNS = (
    Column("asset", "Asset"),
    Column("kind", "Kind", width=16),
    Column("rule", "Rule", width=24),
    Column("due", "Due"),
    Column("in_days", "In d", align="right"),
)


def _last_visit(item: DueItem) -> str:
    visits = item.result.visits
    return visits[-1].isoformat() if visits else "never"


def _why(item: DueItem) -> str:
    reasons = item.result.reasons()
    if reasons:
        return reasons[0]
    return "never visited" if not item.ever_visited else ""


def overdue_table(register: list[DueItem], *, title: str = "Overdue") -> Table:
    """What is already late."""
    table = Table(columns=OVERDUE_COLUMNS, title=title, empty_note="nothing overdue")
    for item in overdue(register):
        table.add(
            asset=item.asset_code,
            kind=str(item.asset_kind),
            rule=item.rule_key,
            last=_last_visit(item),
            due="" if item.next_due is None else item.next_due.isoformat(),
            late=item.days_overdue or None,
            why=_why(item),
        )
    return table


def upcoming_table(
    register: list[DueItem],
    *,
    as_of: dt.date,
    days: int = 90,
    title: str = "Falling due",
) -> Table:
    """What has to be planned for."""
    table = Table(columns=UPCOMING_COLUMNS, title=title, empty_note="nothing due in the window")
    for item in due_within(register, days, as_of=as_of):
        if item.overdue or not item.ever_visited:
            continue
        table.add(
            asset=item.asset_code,
            kind=str(item.asset_kind),
            rule=item.rule_key,
            due="" if item.next_due is None else item.next_due.isoformat(),
            in_days=item.days_until_due,
        )
    return table


def render_compliance(
    register: list[DueItem],
    *,
    as_of: dt.date,
    days: int = 90,
    title: str = "Monitoring compliance",
) -> str:
    """The whole report."""
    rate = compliance_rate(register)
    late = overdue(register)
    header = [
        title,
        f"as at {as_of.isoformat()}",
        "",
        f"{len(register)} asset and rule pairs, {len(late)} overdue",
        f"compliance rate {rate:.1%} of pairs meeting both halves of their rule",
        "",
    ]
    return "\n".join(
        [
            *header,
            overdue_table(register).render(),
            "",
            upcoming_table(register, as_of=as_of, days=days).render(),
        ]
    )
