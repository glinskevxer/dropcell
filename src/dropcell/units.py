"""Unit handling for the quantities a CP survey produces.

Field data arrives in whatever the vendor's logger wrote. The same potential
turns up as ``-0.912 V``, ``-912 mV`` and a bare ``-912``; the same soil
resistivity turns up in ohm-cm from a four pin meter and in ohm-m from a
modelling package. Everything inside dropcell is stored in one canonical unit
per quantity, and the conversion happens once, here, at the edge.

Canonical units:

======================  ==========
quantity                canonical
======================  ==========
potential               millivolt
length                  metre
current                 ampere
area                    square metre
resistivity             ohm-metre
======================  ==========

Sign convention for potentials is the field one. A protected pipe reads
negative against a copper/copper-sulfate cell, so ``-912`` means 912 mV more
negative than the reference and a positive number is an unprotected or
reversed reading rather than an error.
"""

from __future__ import annotations

import re
from typing import Final

from dropcell.errors import UnitError

_NUMBER: Final = re.compile(
    r"""^\s*
    (?P<value>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
    \s*
    (?P<unit>[A-Za-z][A-Za-z0-9./·^-]*)?
    \s*$""",
    re.VERBOSE,
)

POTENTIAL_UNITS: Final[dict[str, float]] = {
    "mv": 1.0,
    "millivolt": 1.0,
    "millivolts": 1.0,
    "v": 1000.0,
    "volt": 1000.0,
    "volts": 1000.0,
}

LENGTH_UNITS: Final[dict[str, float]] = {
    "m": 1.0,
    "metre": 1.0,
    "metres": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "km": 1000.0,
    "ft": 0.3048,
    "feet": 0.3048,
    "foot": 0.3048,
    "mi": 1609.344,
    "mile": 1609.344,
    "miles": 1609.344,
}

CURRENT_UNITS: Final[dict[str, float]] = {
    "a": 1.0,
    "amp": 1.0,
    "amps": 1.0,
    "ampere": 1.0,
    "amperes": 1.0,
    "ma": 0.001,
    "milliamp": 0.001,
    "milliamps": 0.001,
}

AREA_UNITS: Final[dict[str, float]] = {
    "m2": 1.0,
    "cm2": 1e-4,
    "mm2": 1e-6,
    "in2": 0.00064516,
    "ft2": 0.09290304,
}

RESISTIVITY_UNITS: Final[dict[str, float]] = {
    "ohm-m": 1.0,
    "ohm.m": 1.0,
    "ohmm": 1.0,
    "ohm-cm": 0.01,
    "ohm.cm": 0.01,
    "ohmcm": 0.01,
}


def _normalise_unit(raw: str) -> str:
    text = raw.strip().lower().replace("Ω", "ohm").replace("·", ".")
    text = text.replace("^2", "2").replace("²", "2")
    return text.replace(" ", "")


def _convert(text: str, table: dict[str, float], kind: str, default: str) -> float:
    match = _NUMBER.match(text)
    if match is None:
        raise UnitError(f"cannot read a {kind} from this", text=text)
    unit = _normalise_unit(match.group("unit") or default)
    try:
        factor = table[unit]
    except KeyError:
        raise UnitError(
            f"unknown {kind} unit",
            text=text,
            unit=unit,
            known=sorted(table),
        ) from None
    return float(match.group("value")) * factor


def parse_potential_mv(text: str) -> float:
    """Read a structure to electrolyte potential and return millivolts."""
    return _convert(text, POTENTIAL_UNITS, "potential", "mv")


def parse_length_m(text: str) -> float:
    """Read a distance and return metres."""
    return _convert(text, LENGTH_UNITS, "length", "m")


def parse_current_a(text: str) -> float:
    """Read a current and return amperes."""
    return _convert(text, CURRENT_UNITS, "current", "a")


def parse_area_m2(text: str) -> float:
    """Read a coupon or holiday area and return square metres."""
    return _convert(text, AREA_UNITS, "area", "cm2")


def parse_resistivity_ohm_m(text: str) -> float:
    """Read a soil resistivity and return ohm-metres."""
    return _convert(text, RESISTIVITY_UNITS, "resistivity", "ohm-cm")


def current_density_a_per_m2(current_a: float, area_m2: float) -> float:
    """Current density over a coupon of known area."""
    if area_m2 <= 0:
        raise UnitError("coupon area must be positive", area_m2=area_m2)
    return current_a / area_m2


def format_potential_mv(
    millivolts: float, *, unit: str = "mV", places: int | None = None
) -> str:
    """Render a potential the way a survey sheet prints it."""
    normalised = _normalise_unit(unit)
    if normalised not in POTENTIAL_UNITS:
        raise UnitError("unknown potential unit", unit=unit, known=sorted(POTENTIAL_UNITS))
    value = millivolts / POTENTIAL_UNITS[normalised]
    if places is None:
        places = 0 if POTENTIAL_UNITS[normalised] == 1.0 else 3
    return f"{value:.{places}f} {unit}"


def format_length_m(metres: float, *, unit: str = "m", places: int = 2) -> str:
    """Render a distance in whichever unit the report is written in."""
    normalised = _normalise_unit(unit)
    if normalised not in LENGTH_UNITS:
        raise UnitError("unknown length unit", unit=unit, known=sorted(LENGTH_UNITS))
    return f"{metres / LENGTH_UNITS[normalised]:.{places}f} {unit}"
