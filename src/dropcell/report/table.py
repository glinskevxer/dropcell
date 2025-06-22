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
_NO_GROUP = object()


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
    """A table waiting to be rendered.

    A table can carry group headings. They are a break and a label rather than
    a nested structure, because a report that a person reads down a column of
    is a report with one set of column widths, and indenting a group would put
    the numbers in two places.
    """

    columns: Sequence[Column]
    rows: list[dict[str, Any]] = field(default_factory=list)
    title: str = ""
    empty_note: str = "nothing to report"
    group_key: str | None = None
    group_label: str = ""

    def add(self, **values: Any) -> Table:
        """Add one row and return the table, so calls can be chained."""
        self.rows.append(dict(values))
        return self

    def group_by(self, key: str, *, label: str = "") -> Table:
        """Break the rendered table wherever a column's value changes.

        The rows are not reordered. A caller that wants them together sorts
        them, and one that does not gets a break every time the value changes,
        which is occasionally what a report of events in order wants.
        """
        if not any(column.key == key for column in self.columns):
            raise ValidationError("cannot group on a column the table does not have", key=key)
        self.group_key = key
        self.group_label = label
        return self

    def extend(self, rows: Iterable[dict[str, Any]]) -> Table:
        """Add several rows."""
        self.rows.extend(dict(row) for row in rows)
        return self

    def _cells(self) -> list[list[str]]:
        return [
            [
                "" if column.key == self.group_key else column.render(row.get(column.key))
                for column in self.columns
            ]
            for row in self.rows
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
        rule = "  ".join("-" * width for width in widths)
        lines.append(rule)
        previous: Any = _NO_GROUP
        for row, values in zip(cells, self.rows, strict=True):
            if self.group_key is not None:
                current = values.get(self.group_key)
                if current != previous:
                    if previous is not _NO_GROUP:
                        lines.append("")
                    label = self.group_label
                    lines.append(f"{label}{current}" if label else str(current))
                    previous = current
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
