"""The casing record, which is separate from the test that reads it.

A casing test carries the readings; this carries the pipe. Length matters
because a shorted casing is a finding with extent, and reporting a road bore as
a point on the line understates it by however long the crossing is.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station, StationRange


@dataclass(frozen=True)
class Casing:
    """One cased crossing on a line."""

    code: str
    line_code: str
    station: Station
    installed_on: dt.date
    length_m: float = 20.0
    carries: str = ""
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="casing code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if self.length_m <= 0:
            raise ValidationError("a casing has some length", code=self.code)

    @property
    def extent(self) -> StationRange:
        """The stretch of line inside the sleeve."""
        return StationRange(self.station, Station(self.station.metres + self.length_m))
