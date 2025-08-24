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

import codecs
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
    encoding: str = field(default="utf-8", compare=False)
    delimiter: str = field(default=",", compare=False)

    @property
    def separated_by(self) -> str:
        """What the file turned out to be separated by, in words."""
        return {",": "commas", ";": "semicolons", "\t": "tabs", "|": "pipes"}.get(
            self.delimiter, repr(self.delimiter)
        )

    @property
    def needed_a_fallback(self) -> bool:
        """Whether the file was not in the encoding the profile expected."""
        return self.encoding not in {"utf-8", "utf-8-sig"}

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


DELIMITERS = (",", ";", "\t", "|")


def sniff_delimiter(text: str, *, declared: str = ",") -> str:
    """Work out what a file is actually separated by.

    Half of Europe exports CSV separated by semicolons, because the spreadsheet
    is set to a locale where the comma is the decimal point. Those files open
    fine, read as one enormous column, and fail with every required column
    missing, which is the least informative error this package can produce.

    The header row is the only line worth looking at. Data rows contain commas
    inside quoted remarks and semicolons in free text, and counting those
    produces a confident wrong answer. A header row is short, it is written by
    the exporting program rather than by a person, and the separator that
    appears most often in it is the separator.
    """
    line = text.splitlines()[0] if text.splitlines() else ""
    if not line:
        return declared
    counts = {candidate: line.count(candidate) for candidate in DELIMITERS}
    if counts[declared] > 0:
        return declared
    best = max(counts, key=lambda candidate: counts[candidate])
    return best if counts[best] > 0 else declared


def content_hash(payload: bytes) -> str:
    """The fingerprint an import is recognised by."""
    return hashlib.sha256(payload).hexdigest()


def read_text(
    text: str,
    profile: MappingProfile,
    *,
    convention: Convention = Convention.FOOT,
    source: str = "",
    sniff: bool = True,
) -> ReadResult:
    """Read a whole file that is already in memory."""
    payload = text.encode(profile.encoding, errors="replace")
    delimiter = profile.delimiter
    if sniff:
        header_line = "\n".join(text.splitlines()[profile.skip_rows :][:1])
        delimiter = sniff_delimiter(header_line, declared=profile.delimiter)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
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
        delimiter=delimiter,
    )


FALLBACK_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def decode(payload: bytes, encoding: str) -> tuple[str, str]:
    """Decode a file, trying the encodings a survey file actually arrives in.

    Contractors export from a spreadsheet on Windows, and what comes out is
    cp1252 with a byte order mark on the front about half the time. Decoding
    that as UTF-8 with replacement gives a file that reads, imports, and has a
    question mark in the middle of every technician's name, which is the worst
    of the three outcomes because nobody notices.

    So the declared encoding is tried first, then the ones a spreadsheet
    produces, and only then is anything replaced. The encoding that worked is
    handed back, because a file that needed the fallback is worth mentioning.

    A byte order mark is checked for before any of that, because those bytes are
    valid UTF-8 in their own right. Decoding them as plain UTF-8 succeeds, so
    nothing falls through to the encoding that would have stripped them, and the
    mark ends up glued to the front of the first column name.
    """
    if payload.startswith(codecs.BOM_UTF8):
        return payload.decode("utf-8-sig"), "utf-8-sig"
    attempts = (encoding, *FALLBACK_ENCODINGS)
    seen: list[str] = []
    for candidate in attempts:
        if candidate in seen:
            continue
        seen.append(candidate)
        try:
            return payload.decode(candidate), candidate
        except UnicodeDecodeError:
            continue
    return payload.decode(encoding, errors="replace"), f"{encoding} with replacements"


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
    text, used = decode(payload, profile.encoding)
    result = read_text(text, profile, convention=convention, source=target.name)
    return ReadResult(
        profile_name=result.profile_name,
        headers=result.headers,
        rows=result.rows,
        quarantine=result.quarantine,
        content_hash=content_hash(payload),
        source=target.name,
        encoding=used,
        delimiter=result.delimiter,
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
