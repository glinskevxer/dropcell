"""The two lookups every command that names a place on the line was repeating.

Six commands were each doing the same three things: fetch the line, parse the
station in that line's own convention, and refuse it if it falls off the end.
Written out six times it drifted, and two of them had quietly stopped checking
the third part, so a post could be added at station four hundred on a line
eighteen kilometres long and nothing said anything until a report tried to draw
it.
"""

from __future__ import annotations

from dropcell.model.line import Line
from dropcell.stationing import Station
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository


def line_at(database: Database, line_code: str, station: str) -> tuple[Line, Station]:
    """Fetch a line and read a station on it, refusing one off the end."""
    line = LineRepository(database).get(line_code)
    return line, line.require_on_line(Station.parse(station, line.convention))


def line_span(
    database: Database, line_code: str, start: str, end: str | None
) -> tuple[Line, Station, Station]:
    """Fetch a line and read a start and end station on it.

    A missing end is the start, which makes a point finding rather than an
    error. That is the common case for a coating defect, where the survey knows
    where it is and nothing about how far it runs.
    """
    line, first = line_at(database, line_code, start)
    last = first if end is None else line.require_on_line(Station.parse(end, line.convention))
    return line, first, last
