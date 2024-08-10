"""Column mapping, because no two loggers write the same header row.

The same close interval file comes out of one contractor's software with
``Station``, ``P/S On``, ``P/S Off`` and out of another's with ``CHAINAGE``,
``ON_POTENTIAL_MV``, ``INSTANT_OFF``. Neither is wrong. Writing a parser per
contractor means a new parser every time somebody wins a tender, so instead the
file format is described as data and the parser is one.

Headers are matched after folding. Case, spaces, underscores, slashes and the
occasional trailing unit in brackets are all noise that a person typing a
spreadsheet header adds without meaning anything by it, and matching on the raw
string means a file fails to import because somebody capitalised a word.

A mapping refuses a file that is missing a required column, and it says which
one, and it lists what it did find. That last part matters more than it looks:
the usual cause is a file with the columns one row lower than expected, and a
list of the headers actually seen makes that obvious in a second.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import IngestError, ValidationError

_NOISE = re.compile(r"[\s_/\\.\-]+")
_BRACKETED = re.compile(r"\([^)]*\)")


def fold_header(raw: str) -> str:
    """Reduce a header to the part that carries meaning."""
    text = _BRACKETED.sub(" ", raw).strip().lower()
    return _NOISE.sub("", text)


class FieldType(StrEnum):
    """What a column is read as."""

    TEXT = "text"
    STATION = "station"
    POTENTIAL = "potential"
    LENGTH = "length"
    CURRENT = "current"
    VOLTAGE = "voltage"
    RESISTIVITY = "resistivity"
    DATE = "date"
    INTEGER = "integer"
    NUMBER = "number"
    FLAG = "flag"


@dataclass(frozen=True)
class ColumnMapping:
    """One canonical field and the headers that stand for it."""

    field_name: str
    field_type: FieldType
    headers: tuple[str, ...]
    required: bool = True
    default: str | None = None

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise ValidationError("a column mapping needs a field name")
        if not self.headers:
            raise ValidationError(
                "a column mapping needs at least one header", field_name=self.field_name
            )
        if self.required and self.default is not None:
            raise ValidationError(
                "a required column cannot carry a default", field_name=self.field_name
            )

    @property
    def folded_headers(self) -> tuple[str, ...]:
        """The headers this column answers to, folded for matching."""
        return tuple(fold_header(header) for header in self.headers)

    def matches(self, header: str) -> bool:
        """Whether a header in a file stands for this column."""
        return fold_header(header) in self.folded_headers


@dataclass(frozen=True)
class MappingProfile:
    """How to read one contractor's files."""

    name: str
    columns: tuple[ColumnMapping, ...]
    delimiter: str = ","
    encoding: str = "utf-8"
    skip_rows: int = 0
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValidationError("a profile with no columns reads nothing", name=self.name)
        seen: set[str] = set()
        for column in self.columns:
            if column.field_name in seen:
                raise ValidationError(
                    "two columns map to the same field", name=self.name, field=column.field_name
                )
            seen.add(column.field_name)
        if self.skip_rows < 0:
            raise ValidationError("cannot skip a negative number of rows", name=self.name)

    @property
    def required_fields(self) -> tuple[str, ...]:
        """The fields a file has to carry to be readable at all."""
        return tuple(column.field_name for column in self.columns if column.required)

    def column(self, field_name: str) -> ColumnMapping:
        """One column by its canonical field name."""
        for candidate in self.columns:
            if candidate.field_name == field_name:
                return candidate
        raise ValidationError(
            "no column by that field name",
            name=self.name,
            field=field_name,
            known=sorted(item.field_name for item in self.columns),
        )

    def resolve(self, headers: list[str]) -> dict[str, int]:
        """Work out which position in the file each canonical field sits at."""
        found: dict[str, int] = {}
        for position, header in enumerate(headers):
            for column in self.columns:
                if column.field_name in found:
                    continue
                if column.matches(header):
                    found[column.field_name] = position
                    break
        missing = [name for name in self.required_fields if name not in found]
        if missing:
            raise IngestError(
                "the file is missing columns this profile needs",
                profile=self.name,
                missing=missing,
                found=[header.strip() for header in headers],
            )
        return found
