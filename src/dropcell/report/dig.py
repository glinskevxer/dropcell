"""The dig sheet, which is the one piece of paper that leaves the office.

Everything else here is for people who already know what the numbers mean. This
goes to a contractor with an excavator, and what it has to carry is where to
dig, how far along, how deep the pipe is meant to be, what is expected in the
hole, and who to ring when what is in the hole is not that.

The score is printed and so is the arithmetic behind it. A contractor does not
care, but the engineer who is asked why this dig and not the one four hundred
metres along does, and that question is always asked in the field with no
computer to hand.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.analysis.priority import DigBand, PriorityScore, rank
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.report.table import Column, Table
from dropcell.stationing import Station

DIG_COLUMNS = (
    Column("rank", "No", align="right"),
    Column("reference", "Ref"),
    Column("station", "Station", align="right"),
    Column("segment", "Segment"),
    Column("cover", "Cover m", align="right", format=".1f"),
    Column("coating", "Coating", width=16),
    Column("score", "Score", align="right", format=".2f"),
    Column("band", "Band"),
)


@dataclass(frozen=True)
class DigItem:
    """One excavation on the sheet."""

    score: PriorityScore
    station: Station
    segment: Segment

    @property
    def reference(self) -> str:
        """What the defect is called."""
        return self.score.reference

    @property
    def band(self) -> DigBand:
        """Which band it fell in."""
        return self.score.band


def dig_table(
    line: Line,
    items: list[DigItem],
    *,
    title: str = "Dig sheet",
) -> Table:
    """Build the table of excavations."""
    table = Table(columns=DIG_COLUMNS, title=title, empty_note="nothing to dig")
    ordered = sorted(
        items,
        key=lambda item: (-item.score.score, item.reference),
    )
    for position, item in enumerate(ordered, start=1):
        table.add(
            rank=position,
            reference=item.reference,
            station=line.format_station(item.station),
            segment=item.segment.code,
            cover=item.segment.depth_of_cover_m,
            coating=str(item.segment.coating),
            score=item.score.score,
            band=str(item.band),
        )
    return table


def render_dig_sheet(
    line: Line,
    items: list[DigItem],
    *,
    as_of: dt.date,
    contact: str = "",
    budget: int | None = None,
) -> str:
    """The whole sheet, with the scoring written out underneath."""
    chosen = list(items)
    ranked = rank([item.score for item in chosen])
    if budget is not None:
        keep = {score.reference for score in ranked[:budget]}
        chosen = [item for item in chosen if item.reference in keep]
    header = [
        f"Dig sheet, {line.code} {line.name}",
        f"raised {as_of.isoformat()}",
        f"operator {line.operator}",
        f"commodity {line.commodity}",
    ]
    if contact:
        header.append(f"call {contact} before breaking ground")
    header.append("")
    body = [dig_table(line, chosen, title="Excavations").render(), ""]
    body.append("How each score was reached")
    body.append("")
    for score in rank([item.score for item in chosen]):
        body.append(f"  {score.explain()}")
    return "\n".join([*header, *body])
