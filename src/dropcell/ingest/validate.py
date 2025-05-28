"""Checking a file before anybody tries to load it.

A survey file arrives by email at four on a Friday. Whoever sent it has gone
home. The useful thing to be able to do in that moment is find out whether it
will load on Monday, and the useless thing is to load it, get a conflict on the
third row, and have to work out from the error which of eleven things went
wrong.

So this reads a file against every profile that ships, reports which ones it
could be, and for the best match says exactly what would happen. It writes
nothing and it opens no register, which is what makes it safe to run against
something somebody has just sent you.

The column report is the part that earns its keep. Nine times out of ten a file
that will not load has one column named something nobody has seen before, and
listing the headers beside the fields they matched turns a ten minute puzzle
into a glance.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.errors import IngestError
from dropcell.ingest.mapping import MappingProfile
from dropcell.ingest.profiles import PROFILES, get_profile
from dropcell.ingest.reader import ReadResult, read_text
from dropcell.stationing import Convention


@dataclass(frozen=True)
class ProfileMatch:
    """What one profile made of a file."""

    profile: str
    readable: bool
    accepted: int
    rejected: int
    missing: tuple[str, ...]
    matched: tuple[tuple[str, str], ...]
    unmatched_headers: tuple[str, ...]

    @property
    def score(self) -> tuple[int, int, int]:
        """How good a match this is, best last."""
        return (int(self.readable), self.accepted, -len(self.unmatched_headers))


def headers_of(text: str, profile: MappingProfile) -> list[str]:
    """The header row a profile would read, after any rows it skips."""
    lines = text.splitlines()[profile.skip_rows :]
    if not lines:
        return []
    return [cell.strip() for cell in lines[0].split(profile.delimiter)]


def try_profile(
    text: str,
    profile: MappingProfile,
    *,
    convention: Convention = Convention.FOOT,
) -> ProfileMatch:
    """Read a file against one profile without writing anything."""
    headers = headers_of(text, profile)
    matched: list[tuple[str, str]] = []
    used: set[int] = set()
    for position, header in enumerate(headers):
        for column in profile.columns:
            if column.matches(header):
                matched.append((header, column.field_name))
                used.add(position)
                break
    unmatched = tuple(header for position, header in enumerate(headers) if position not in used)
    try:
        result: ReadResult | None = read_text(text, profile, convention=convention)
    except IngestError as error:
        return ProfileMatch(
            profile=profile.name,
            readable=False,
            accepted=0,
            rejected=0,
            missing=tuple(str(item) for item in error.detail.get("missing", ())),
            matched=tuple(matched),
            unmatched_headers=unmatched,
        )
    assert result is not None
    return ProfileMatch(
        profile=profile.name,
        readable=True,
        accepted=result.accepted,
        rejected=result.rejected,
        missing=(),
        matched=tuple(matched),
        unmatched_headers=unmatched,
    )


def identify(
    text: str,
    *,
    convention: Convention = Convention.FOOT,
) -> list[ProfileMatch]:
    """Try every profile this build ships and report all of them, best first."""
    matches = [
        try_profile(text, get_profile(name), convention=convention) for name in sorted(PROFILES)
    ]
    return sorted(matches, key=lambda item: item.score, reverse=True)


def best_match(
    text: str,
    *,
    convention: Convention = Convention.FOOT,
) -> ProfileMatch | None:
    """The profile most likely to be the right one, or nothing if none read."""
    found = identify(text, convention=convention)
    if not found or not found[0].readable:
        return None
    return found[0]
