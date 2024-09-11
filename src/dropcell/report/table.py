"""Plain text tables, because the output of this goes in an email.

Nothing here draws a box. A report that has to survive being pasted into a
message, printed by somebody's field supervisor, and read in a terminal that is
eighty columns wide is a report made of spaces and one rule under the header.

Numbers are right aligned and text is left aligned, because that is what makes a
column of potentials scannable. A number that will not fit is not truncated,
because a truncated number is a wrong number rather than a shortened one; the
column widens instead. Text that will not fit is truncated with a marker, which
is honest because a shortened word still looks shortened.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from dropcell.errors import ValidationError

ELLIPSIS = "…"


@dataclass(frozen=True)
class Column:
    """One column of a table."""

    key: str
    heading: str
    align: str = "left"
    width: int | None = None
    format: str = ""

    def __post_init__(self) -> None:
        if self.align not in {"left", "right"}:
            raise ValidationError(
                "a column is aligned left or right", key=self.key, align=self.align
            )
        if self.width is not None and self.width < 1:
            raise ValidationError("a column width is at least one", key=self.key)

    @property
    def numeric(self) -> bool:
        """Whether this column holds numbers that must not be shortened."""
        return self.align == "right"

    def render(self, value: Any) -> str:
        """Turn one cell value into the text that goes in the column."""
        if value is None:
            return ""
        if self.format:
            return format(value, self.format)
        return str(value)


def truncate(text: str, width: int) -> str:
    """Shorten text to a width, marking that it was shortened."""
    if width < 1:
        raise ValidationError("cannot truncate to nothing", width=width)
    if len(text) <= width:
        return text
    if width == 1:
        return ELLIPSIS
    return text[: width - 1] + ELLIPSIS


@dataclass
class Table:
    """A table waiting to be rendered."""

    columns: Sequence[Column]
    rows: list[dict[str, Any]] = field(default_factory=list)
    title: str = ""
    empty_note: str = "nothing to report"

    def add(self, **values: Any) -> Table:
        """Add one row and return the table, so calls can be chained."""
        self.rows.append(dict(values))
        return self

    def extend(self, rows: Iterable[dict[str, Any]]) -> Table:
        """Add several rows."""
        self.rows.extend(dict(row) for row in rows)
        return self

    def _cells(self) -> list[list[str]]:
        return [
            [column.render(row.get(column.key)) for column in self.columns] for row in self.rows
        ]

    def _widths(self, cells: list[list[str]]) -> list[int]:
        widths: list[int] = []
        for index, column in enumerate(self.columns):
            longest = max(
                [len(column.heading)] + [len(row[index]) for row in cells],
                default=len(column.heading),
            )
            if column.width is not None and not column.numeric:
                widths.append(min(longest, column.width))
            else:
                widths.append(longest)
        return widths

    def render(self) -> str:
        """Render the whole table."""
        lines: list[str] = []
        if self.title:
            lines.append(self.title)
            lines.append("")
        if not self.rows:
            lines.append(self.empty_note)
            return "\n".join(lines)
        cells = self._cells()
        widths = self._widths(cells)
        header = "  ".join(
            _pad(column.heading, width, column.align)
            for column, width in zip(self.columns, widths, strict=True)
        )
        lines.append(header.rstrip())
        lines.append("  ".join("-" * width for width in widths))
        for row in cells:
            lines.append(
                "  ".join(
                    _pad(_fit(value, width, column), width, column.align)
                    for value, width, column in zip(row, widths, self.columns, strict=True)
                ).rstrip()
            )
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render()


def _fit(value: str, width: int, column: Column) -> str:
    if column.numeric or len(value) <= width:
        return value
    return truncate(value, width)


def _pad(value: str, width: int, align: str) -> str:
    if align == "right":
        return value.rjust(width)
    return value.ljust(width)
