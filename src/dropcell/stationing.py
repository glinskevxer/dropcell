"""Position along a pipeline, and the two ways the industry writes it.

A pipeline has no useful coordinate other than how far along it you are. That
distance is written as a station: ``12+45.50`` on a line surveyed in feet means
twelve hundred and forty five and a half feet from the origin, and ``1+000.0``
on a line surveyed in metres means one kilometre. The part in front of the plus
counts whole major units, the part behind it counts minor units inside one.

Both conventions collapse onto metres inside dropcell. A ``Station`` is that
distance and nothing else, so two readings taken on the same line can be
compared without caring which crew's sheet they came off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dropcell.errors import StationError
from dropcell.units import parse_length_m

_STATION_TEXT: Final = re.compile(
    r"^\s*(?P<sign>-)?(?P<major>\d+)\s*\+\s*(?P<minor>\d+(?:\.\d+)?)\s*$"
)


class Convention(StrEnum):
    """How a line's stationing is written down."""

    FOOT = "foot"
    METRIC = "metric"

    @property
    def minor_metres(self) -> float:
        """Length of one minor unit, the part written after the plus."""
        return 0.3048 if self is Convention.FOOT else 1.0

    @property
    def minors_per_major(self) -> int:
        """How many minor units fill one major unit."""
        return 100 if self is Convention.FOOT else 1000

    @property
    def major_metres(self) -> float:
        """Length of one major unit, the part written before the plus."""
        return self.minor_metres * self.minors_per_major

    @property
    def minor_digits(self) -> int:
        """Width the minor part is zero padded to when printed."""
        return 2 if self is Convention.FOOT else 3

    @property
    def minor_places(self) -> int:
        """Decimal places kept on the minor part when printed."""
        return 2 if self is Convention.FOOT else 1


@dataclass(frozen=True, order=True)
class Station:
    """A distance along the line, held in metres from the line origin."""

    metres: float

    def __post_init__(self) -> None:
        if not isinstance(self.metres, int | float):
            raise StationError("station must be a number", metres=self.metres)
        object.__setattr__(self, "metres", float(self.metres))

    @classmethod
    def parse(cls, text: str, convention: Convention = Convention.FOOT) -> Station:
        """Read either a plus separated station or a plain distance with a unit."""
        match = _STATION_TEXT.match(text)
        if match is None:
            if "+" in text.strip()[1:]:
                raise StationError("station is not in major+minor form", text=text)
            try:
                return cls(parse_length_m(text))
            except Exception as exc:
                raise StationError("cannot read a station from this", text=text) from exc
        minor = float(match.group("minor"))
        if minor >= convention.minors_per_major:
            raise StationError(
                "minor part overflows one major unit",
                text=text,
                minor=minor,
                limit=convention.minors_per_major,
            )
        major = int(match.group("major"))
        total = major * convention.minors_per_major + minor
        if match.group("sign"):
            total = -total
        return cls(total * convention.minor_metres)

    def format(self, convention: Convention = Convention.FOOT) -> str:
        """Write the station back out in the convention the line is surveyed in."""
        minors = self.metres / convention.minor_metres
        sign = "-" if minors < 0 else ""
        minors = abs(minors)
        major, minor = divmod(minors, convention.minors_per_major)
        rounded = round(minor, convention.minor_places)
        if rounded >= convention.minors_per_major:
            major += 1
            rounded = 0.0
        width = convention.minor_digits + convention.minor_places + 1
        return f"{sign}{int(major)}+{rounded:0{width}.{convention.minor_places}f}"

    def to(self, other: Station) -> float:
        """Signed distance in metres from this station to another."""
        return other.metres - self.metres

    def shifted(self, metres: float) -> Station:
        """A new station that many metres further along the line."""
        return Station(self.metres + metres)

    def __str__(self) -> str:
        return self.format()
