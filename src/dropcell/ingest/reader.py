"""Reading a delimited file through a profile, and quarantining what will not read.

A survey file has forty thousand rows in it and three of them are broken. The
useless behaviours are to abort the whole import on the first bad row, which
loses thirty nine thousand nine hundred and ninety seven good readings, and to
skip bad rows silently, which loses the three without telling anybody.

So bad rows are set aside with the reason and the row number, the good ones go
through, and the caller gets both. What to do about a file that is nine tenths
quarantine is a decision the caller makes, because the answer differs between a
nightly load and somebody at a terminal who can go and fetch the right file.

The content hash is of the bytes as they arrived. It is what makes an import
idempotent, and it has to be the raw bytes rather than anything derived from
the parsed rows, so that a file which parses differently after a profile change
is still recognised as the same file.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dropcell.errors import IngestError
from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile
from dropcell.ingest.values import coerce
from dropcell.stationing import Convention


@dataclass(frozen=True)
class RowError:
    """One thing wrong with one row."""

    field_name: str
    message: str
    raw: str


@dataclass(frozen=True)
class QuarantinedRow:
    """A row that could not be read, kept with the reasons."""

    row_number: int
    raw: tuple[str, ...]
    errors: tuple[RowError, ...]

    @property
    def summary(self) -> str:
        """One line naming the row and what is wrong with it."""
        reasons = "; ".join(f"{item.field_name}: {item.message}" for item in self.errors)
        return f"row {self.row_number}: {reasons}"


@dataclass(frozen=True)
class ReadResult:
    """Everything one pass over a file produced."""

    profile_name: str
    headers: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    quarantine: tuple[QuarantinedRow, ...]
    content_hash: str
    source: str = field(default="", compare=False)

    @property
    def accepted(self) -> int:
        """How many rows came through."""
        return len(self.rows)

    @property
    def rejected(self) -> int:
        """How many rows were set aside."""
        return len(self.quarantine)

    @property
    def total(self) -> int:
        """How many data rows the file held."""
        return self.accepted + self.rejected

    @property
    def acceptance_rate(self) -> float:
        """The share of rows that read cleanly."""
        return 1.0 if self.total == 0 else self.accepted / self.total

    def require_acceptance(self, minimum: float) -> None:
        """Refuse a result that is mostly quarantine."""
        if self.acceptance_rate < minimum:
            raise IngestError(
                "too much of this file could not be read",
                profile=self.profile_name,
                accepted=self.accepted,
                rejected=self.rejected,
                acceptance_rate=self.acceptance_rate,
                minimum=minimum,
            )


def content_hash(payload: bytes) -> str:
    """The fingerprint an import is recognised by."""
    return hashlib.sha256(payload).hexdigest()


def read_text(
    text: str,
    profile: MappingProfile,
    *,
    convention: Convention = Convention.FOOT,
    source: str = "",
) -> ReadResult:
    """Read a whole file that is already in memory."""
    payload = text.encode(profile.encoding, errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=profile.delimiter)
    lines = list(reader)
    if profile.skip_rows:
        lines = lines[profile.skip_rows :]
    if not lines:
        raise IngestError("the file has no header row", profile=profile.name, source=source)
    headers = [cell.strip() for cell in lines[0]]
    positions = profile.resolve(headers)
    rows: list[dict[str, Any]] = []
    quarantine: list[QuarantinedRow] = []
    for offset, raw in enumerate(lines[1:], start=profile.skip_rows + 2):
        if not any(cell.strip() for cell in raw):
            continue
        parsed, errors = _read_row(raw, profile, positions, convention)
        if errors:
            quarantine.append(
                QuarantinedRow(row_number=offset, raw=tuple(raw), errors=tuple(errors))
            )
            continue
        rows.append(parsed)
    return ReadResult(
        profile_name=profile.name,
        headers=tuple(headers),
        rows=tuple(rows),
        quarantine=tuple(quarantine),
        content_hash=content_hash(payload),
        source=source,
    )


def read_file(
    path: Path | str,
    profile: MappingProfile,
    *,
    convention: Convention = Convention.FOOT,
) -> ReadResult:
    """Read a file off disk."""
    target = Path(path)
    try:
        payload = target.read_bytes()
    except OSError as exc:
        raise IngestError("cannot read that file", path=str(target)) from exc
    text = payload.decode(profile.encoding, errors="replace")
    result = read_text(text, profile, convention=convention, source=target.name)
    return ReadResult(
        profile_name=result.profile_name,
        headers=result.headers,
        rows=result.rows,
        quarantine=result.quarantine,
        content_hash=content_hash(payload),
        source=target.name,
    )


def _default_value(column: ColumnMapping, convention: Convention) -> Any:
    """The value a column takes when the file does not carry it at all.

    A default is a literal rather than a cell, so an empty string in a text
    column means an empty string. A blank cell in the same column means nothing
    was recorded, and the two are not the same fact.
    """
    if column.default is None:
        return None
    value = coerce(column.default, column.field_type, convention=convention)
    if value is None and column.field_type is FieldType.TEXT:
        return column.default
    return value


def _read_row(
    raw: list[str],
    profile: MappingProfile,
    positions: dict[str, int],
    convention: Convention,
) -> tuple[dict[str, Any], list[RowError]]:
    parsed: dict[str, Any] = {}
    errors: list[RowError] = []
    for column in profile.columns:
        position = positions.get(column.field_name)
        if position is None:
            parsed[column.field_name] = _default_value(column, convention)
            continue
        if position >= len(raw):
            if column.required:
                errors.append(
                    RowError(column.field_name, "the row is short of this column", "")
                )
            else:
                parsed[column.field_name] = None
            continue
        cell = raw[position]
        try:
            value = coerce(cell, column.field_type, convention=convention)
        except IngestError as exc:
            errors.append(RowError(column.field_name, exc.message, cell))
            continue
        if value is None and column.required:
            errors.append(RowError(column.field_name, "this column cannot be empty", cell))
            continue
        parsed[column.field_name] = value
    return parsed, errors
