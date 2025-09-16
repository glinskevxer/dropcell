"""The one page that answers what to do next.

Everything else here answers a question somebody knew to ask. This answers the
question they actually have, which is that they have half a day and thirty
pages and no idea which of them matters this week.

It is deliberately short and it is deliberately mixed. The five things on it
come from five different parts of the tool and they are ranked against each
other, because a rectifier that has been dead for four months and a coating
defect due next week are competing for the same person's Tuesday, and no report
that keeps them on separate pages helps with that.

Nothing here is new information. Every line of it is on another page already,
which is the point: the value is in the ranking, and the ranking is the thing
the other pages cannot do because each of them only knows about its own corner.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from dropcell.analysis.view import LineView
from dropcell.report.table import Column, Table

NEXT_COLUMNS = (
    Column("rank", "No", align="right"),
    Column("urgency", "Urgency", width=10),
    Column("what", "What", width=46),
    Column("where", "Where", width=18),
    Column("why", "Why now", width=44),
)


class Urgency(StrEnum):
    """How soon a thing needs somebody."""

    NOW = "now"
    THIS_MONTH = "this month"
    THIS_YEAR = "this year"

    @property
    def rank(self) -> int:
        """An order to sort by, soonest first."""
        return {"now": 0, "this month": 1, "this year": 2}[self.value]


@dataclass(frozen=True)
class NextItem:
    """One thing to do."""

    urgency: Urgency
    what: str
    where: str
    why: str
    days_over: int = 0

    @property
    def sort_key(self) -> tuple[int, int, str]:
        """Soonest first, then whatever is furthest past its date."""
        return (self.urgency.rank, -self.days_over, self.what)


def from_view(view: LineView, *, as_of: dt.date, limit: int = 10) -> list[NextItem]:
    """Pull the handful of things that matter out of one line's whole state."""
    items: list[NextItem] = []
    for finding in view.open_findings:
        if finding.is_overdue(as_of):
            assert finding.due_by is not None
            over = (as_of - finding.due_by).days
            items.append(
                NextItem(
                    urgency=Urgency.NOW,
                    what=f"{finding.code} {finding.kind}",
                    where=finding.extent.start.format(view.line.convention),
                    why=f"{over} days past its date of {finding.due_by.isoformat()}",
                    days_over=over,
                )
            )
    for item in view.overdue:
        if not item.ever_visited:
            items.append(
                NextItem(
                    urgency=Urgency.NOW,
                    what=f"{item.asset_code} has never been read",
                    where=str(item.asset_kind),
                    why=f"the {item.rule_key} rule has never been satisfied",
                    days_over=10**6,
                )
            )
            continue
        items.append(
            NextItem(
                urgency=Urgency.THIS_MONTH,
                what=f"{item.asset_code} is overdue",
                where=str(item.asset_kind),
                why=f"{item.days_overdue} days past the {item.rule_key} interval",
                days_over=item.days_overdue,
            )
        )
    for post in view.assessment.under_criterion if view.assessment else ():
        items.append(
            NextItem(
                urgency=Urgency.THIS_MONTH,
                what=f"{post.code} is under criterion",
                where=view.line.format_station(post.post.station),
                why="no criterion was met at the last reading",
            )
        )
    for post in view.assessment.stale if view.assessment else ():
        items.append(
            NextItem(
                urgency=Urgency.THIS_YEAR,
                what=f"{post.code} was last read {post.reading_age_days} days ago",
                where=view.line.format_station(post.post.station),
                why="the verdict on it rests on a reading over fifteen months old",
            )
        )
    gap = view.coverage.longest_gap
    if gap is not None and gap.length_m > view.coverage.reach_m:
        items.append(
            NextItem(
                urgency=Urgency.THIS_YEAR,
                what=f"{gap.length_m:.0f} m of line has no post within reach",
                where=gap.extent.start.format(view.line.convention),
                why="nothing on this stretch is measured at all",
            )
        )
    return sorted(items, key=lambda item: item.sort_key)[:limit]


def render_next(view: LineView, *, as_of: dt.date, limit: int = 10) -> str:
    """The whole page."""
    items = from_view(view, as_of=as_of, limit=limit)
    table = Table(
        columns=NEXT_COLUMNS,
        title=f"What to do next, {view.line.code}",
        empty_note="nothing on this line is asking for anybody",
    )
    for position, item in enumerate(items, start=1):
        table.add(
            rank=position,
            urgency=str(item.urgency),
            what=item.what,
            where=item.where,
            why=item.why,
        )
    now = sum(1 for item in items if item.urgency is Urgency.NOW)
    return "\n".join(
        [
            f"as at {as_of.isoformat()}",
            "",
            table.render(),
            "",
            f"{now} of these will not wait",
            "everything here is on another page already; the ranking is the point",
        ]
    )
