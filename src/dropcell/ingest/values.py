"""Turning the text in a cell into the thing it stands for.

A cell holds a string. What that string means depends on the column it is in,
and there are only so many kinds of column, so the conversion is a small table
rather than a pile of special cases at every call site.

Two decisions worth stating. A blank cell is nothing, not zero. A logger that
could not read a post writes an empty cell, and turning that into a zero
millivolt reading manufactures a catastrophic potential out of a missing one.

And a date with no century, or with the day and the month the other way round,
is refused rather than guessed. Half the dates in the world are ambiguous and
picking a convention silently means every file imported from the other side of
the Atlantic is wrong by up to eleven months with nothing to show for it.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from dropcell.errors import IngestError
from dropcell.ingest.mapping import FieldType
from dropcell.stationing import Convention, Station
from dropcell.units import (
    parse_area_m2,
    parse_current_a,
    parse_length_m,
    parse_potential_mv,
    parse_resistivity_ohm_m,
    parse_voltage_v,
)

TRUE_WORDS = frozenset({"y", "yes", "true", "t", "1", "x", "on"})
FALSE_WORDS = frozenset({"n", "no", "false", "f", "0", "off", ""})

DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y", "%Y%m%d")


def parse_date(text: str) -> dt.date:
    """Read a date in one of the unambiguous formats, and refuse the rest."""
    cleaned = text.strip()
    for pattern in DATE_FORMATS:
        try:
            return dt.datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    raise IngestError(
        "this date is not in a format that can be read without guessing",
        text=cleaned,
        accepted=list(DATE_FORMATS),
    )


def parse_flag(text: str) -> bool:
    """Read one of the many ways a spreadsheet writes yes and no."""
    cleaned = text.strip().lower()
    if cleaned in TRUE_WORDS:
        return True
    if cleaned in FALSE_WORDS:
        return False
    raise IngestError("this is not a yes or a no", text=text)


def coerce(
    text: str,
    field_type: FieldType,
    *,
    convention: Convention = Convention.FOOT,
) -> Any:
    """Turn one cell into the value its column stands for."""
    cleaned = text.strip()
    if not cleaned and field_type is not FieldType.FLAG:
        return None
    try:
        return _CONVERTERS[field_type](cleaned, convention)
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError(
            "this cell does not hold what its column says it does",
            text=text,
            field_type=str(field_type),
            reason=str(exc),
        ) from exc


def _text(value: str, _: Convention) -> str:
    return value


def _station(value: str, convention: Convention) -> Station:
    return Station.parse(value, convention)


def _potential(value: str, _: Convention) -> float:
    return parse_potential_mv(value)


def _length(value: str, _: Convention) -> float:
    return parse_length_m(value)


def _current(value: str, _: Convention) -> float:
    return parse_current_a(value)


def _voltage(value: str, _: Convention) -> float:
    return parse_voltage_v(value)


def _resistivity(value: str, _: Convention) -> float:
    return parse_resistivity_ohm_m(value)


def _date(value: str, _: Convention) -> dt.date:
    return parse_date(value)


def _integer(value: str, _: Convention) -> int:
    return int(value.replace(",", ""))


def _number(value: str, _: Convention) -> float:
    return float(value.replace(",", ""))


def _flag(value: str, _: Convention) -> bool:
    return parse_flag(value)


def _area(value: str, _: Convention) -> float:
    return parse_area_m2(value)


_CONVERTERS: dict[FieldType, Any] = {
    FieldType.TEXT: _text,
    FieldType.STATION: _station,
    FieldType.POTENTIAL: _potential,
    FieldType.LENGTH: _length,
    FieldType.CURRENT: _current,
    FieldType.VOLTAGE: _voltage,
    FieldType.RESISTIVITY: _resistivity,
    FieldType.DATE: _date,
    FieldType.INTEGER: _integer,
    FieldType.NUMBER: _number,
    FieldType.FLAG: _flag,
}

__all__ = ["DATE_FORMATS", "coerce", "parse_date", "parse_flag"]
