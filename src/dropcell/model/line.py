"""A pipeline, which is the thing everything else hangs off.

A line is a named run of steel with one stationing convention, one operator and
one commodity. Diameter and wall vary along a real line, so those live on the
segment; what the line carries is the nominal size the drawings were made at
and the length the stationing runs to.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.errors import ValidationError
from dropcell.model.enums import Commodity, LineStatus
from dropcell.model.ids import normalise_code
from dropcell.stationing import Convention, Station, StationRange

EARLIEST_INSTALL_YEAR = 1850
MM_PER_INCH = 25.4


@dataclass(frozen=True)
class Line:
    """One pipeline under cathodic protection."""

    code: str
    name: str
    operator: str
    commodity: Commodity
    length_m: float
    nominal_diameter_mm: float
    installed_year: int
    convention: Convention = Convention.FOOT
    status: LineStatus = LineStatus.IN_SERVICE
    retired_on: dt.date | None = None
    notes: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="line code"))
        for label, value in (("name", self.name), ("operator", self.operator)):
            if not value.strip():
                raise ValidationError(f"line {label} cannot be blank", code=self.code)
            object.__setattr__(self, label, value.strip())
        if self.length_m <= 0:
            raise ValidationError("line length must be positive", code=self.code)
        if self.nominal_diameter_mm <= 0:
            raise ValidationError("line diameter must be positive", code=self.code)
        this_year = dt.date.today().year
        if not EARLIEST_INSTALL_YEAR <= self.installed_year <= this_year:
            raise ValidationError(
                "install year is outside the range a pipeline can have",
                code=self.code,
                year=self.installed_year,
            )
        if self.status is LineStatus.IN_SERVICE and self.retired_on is not None:
            raise ValidationError("a line in service has not been retired", code=self.code)
        if self.status is not LineStatus.IN_SERVICE and self.retired_on is None:
            raise ValidationError(
                "a retired line needs the date it came out of service", code=self.code
            )
        if self.retired_on is not None and self.retired_on.year < self.installed_year:
            raise ValidationError("a line cannot be retired before it went in", code=self.code)

    @property
    def is_monitored(self) -> bool:
        """Whether the monitoring rules still apply to this line."""
        return self.status.is_monitored

    @property
    def extent(self) -> StationRange:
        """The whole line, origin to end."""
        return StationRange(Station(0.0), Station(self.length_m))

    @property
    def nominal_diameter_in(self) -> float:
        """Diameter in inches, which is what the line is called in conversation."""
        return self.nominal_diameter_mm / MM_PER_INCH

    @property
    def age_years(self) -> int:
        """How long the line has been in the ground, to the nearest whole year."""
        return dt.date.today().year - self.installed_year

    def station(self, text: str) -> Station:
        """Read a station in this line's own convention."""
        return Station.parse(text, self.convention)

    def span(self, text: str) -> StationRange:
        """Read a station range in this line's own convention."""
        return StationRange.parse(text, self.convention)

    def format_station(self, station: Station) -> str:
        """Write a station out the way this line's sheets print it."""
        return station.format(self.convention)

    def covers(self, station: Station) -> bool:
        """Whether a station falls on this line at all."""
        return self.extent.contains(station)

    def require_on_line(self, station: Station) -> Station:
        """Return the station, or refuse it if it is off the end of the line."""
        if not self.covers(station):
            raise ValidationError(
                "station is not on this line",
                code=self.code,
                station=self.format_station(station),
                length_m=self.length_m,
            )
        return station
