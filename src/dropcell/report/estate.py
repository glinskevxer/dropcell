"""Every line on one page, which is the view nobody in the field ever wants.

A CP engineer works a line at a time. The person who decides how many engineers
there are works the whole estate at once, and the question they ask is which
line is in the worst state, not which post.

Ranking lines against each other is harder than it looks and the trap is
length. A twenty kilometre line with four failing posts and a two kilometre line
with four failing posts are not in the same condition, and every figure that
counts posts says they are. So the counts are here for reading and the ordering
is on rate and on exposure, both of which divide by something.

A line with nothing on it at all is on the page. An estate summary that quietly
leaves out the lines nobody has built a register for is exactly the report that
lets those lines stay unbuilt.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.report.table import Column, Table

ESTATE_COLUMNS = (
    Column("operator", "Operator", width=20),
    Column("code", "Line"),
    Column("name", "Name", width=24),
    Column("length", "Length km", align="right", format=".1f"),
    Column("posts", "Posts", align="right"),
    Column("judged", "Judged", align="right"),
    Column("protected", "Protected", align="right"),
    Column("rate", "Rate", align="right", format=".0%"),
    Column("unread", "Unread", align="right"),
    Column("overdue", "Overdue", align="right"),
    Column("findings", "Open", align="right"),
    Column("state", "State", width=16),
)


@dataclass(frozen=True)
class LineSummary:
    """One line's figures for the estate page."""

    code: str
    name: str
    operator: str
    length_m: float
    posts: int
    judged: int
    protected: int
    unread: int
    overdue: int
    open_findings: int

    @property
    def rate(self) -> float | None:
        """The share of judged posts that met a criterion."""
        return None if self.judged == 0 else self.protected / self.judged

    @property
    def state(self) -> str:
        """A word for the line, chosen so no two mean the same thing."""
        if self.posts == 0:
            return "no posts"
        if self.judged == 0:
            return "never read"
        if self.unread and self.unread >= self.posts / 2:
            return "half unread"
        rate = self.rate
        assert rate is not None
        if rate < 0.8:
            return "under criterion"
        if self.overdue:
            return "behind"
        return "in hand"

    @property
    def sort_key(self) -> tuple[int, float, str]:
        """Lines nobody has built come first, then the worst rate."""
        if self.posts == 0 or self.judged == 0:
            return (0, 0.0, self.code)
        rate = self.rate
        assert rate is not None
        return (1, rate, self.code)


def render_estate(
    summaries: list[LineSummary],
    *,
    as_of: dt.date,
    by_operator: bool = False,
) -> str:
    """The whole estate on one page.

    Grouped by operator it reads as a set of relationships, which is what a
    contractor holding registers for six clients wants. Ungrouped it reads as
    one estate ranked worst first, which is what an operator with six lines
    wants. Neither is the default for the other.
    """
    table = Table(
        columns=ESTATE_COLUMNS,
        title="Estate",
        empty_note="no lines in the register",
    )
    ordered = (
        sorted(summaries, key=lambda item: (item.operator, *item.sort_key))
        if by_operator
        else sorted(summaries, key=lambda item: item.sort_key)
    )
    if by_operator:
        table.group_by("operator")
    for summary in ordered:
        table.add(
            operator=summary.operator,
            code=summary.code,
            name=summary.name,
            length=summary.length_m / 1000.0,
            posts=summary.posts,
            judged=summary.judged,
            protected=summary.protected,
            rate=summary.rate,
            unread=summary.unread or None,
            overdue=summary.overdue or None,
            findings=summary.open_findings or None,
            state=summary.state,
        )
    total_length = sum(item.length_m for item in summaries) / 1000.0
    judged = sum(item.judged for item in summaries)
    protected = sum(item.protected for item in summaries)
    unbuilt = sum(1 for item in summaries if item.posts == 0)
    operators = len({item.operator for item in summaries})
    rate = 0.0 if judged == 0 else protected / judged
    return "\n".join(
        [
            f"as at {as_of.isoformat()}",
            "",
            table.render(),
            "",
            f"{len(summaries)} lines across {operators} operators, {total_length:.1f} km, "
            f"{unbuilt} with no posts on them at all",
            f"{protected} of {judged} judged posts across the estate met a criterion"
            f" ({rate:.1%})",
        ]
    )
