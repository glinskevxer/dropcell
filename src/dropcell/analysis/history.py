"""Comparing one year of a line against the years before it.

A single year's protection rate is a number with no scale. Ninety two percent
is excellent on an old bare line and alarming on a three year old epoxy one,
and the only thing that reliably distinguishes them is what the same line read
last year and the year before.

The comparison is made post by post rather than on the rates. Two years can
produce the same rate with completely different posts failing, which is a
system that has been rebalanced rather than one that is stable, and a rate on
its own cannot show the difference. So what comes out is a set of posts that
changed sides, and the count of them is the number worth reading.

Posts that were not read in one of the two years are held out of the
comparison entirely. Counting an unread post as a change makes a year where
somebody was ill look like a year where the pipe moved.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.criteria.potential import DEFAULT_PROTECTION_MV
from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.reading import Reading


@dataclass(frozen=True)
class YearReading:
    """One post's best reading in one year."""

    test_point_code: str
    year: int
    off_mv: float

    def meets(self, threshold_mv: float = DEFAULT_PROTECTION_MV) -> bool:
        """Whether this reading satisfied the criterion."""
        return self.off_mv <= threshold_mv


@dataclass(frozen=True)
class Change:
    """One post that read differently in two years."""

    test_point_code: str
    was_mv: float
    now_mv: float

    @property
    def movement_mv(self) -> float:
        """How far the post moved, positive meaning less protected."""
        return self.now_mv - self.was_mv


@dataclass(frozen=True)
class YearOnYear:
    """Two years of one line, compared post by post."""

    line_code: str
    earlier_year: int
    later_year: int
    threshold_mv: float
    compared: tuple[str, ...]
    lost: tuple[Change, ...]
    gained: tuple[Change, ...]
    held: tuple[str, ...]
    only_earlier: tuple[str, ...]
    only_later: tuple[str, ...]

    @property
    def net(self) -> int:
        """How many more posts pass than did, which can be nought while both move."""
        return len(self.gained) - len(self.lost)

    @property
    def churn(self) -> int:
        """How many posts changed sides at all."""
        return len(self.gained) + len(self.lost)

    @property
    def stable(self) -> bool:
        """Whether nothing changed sides."""
        return self.churn == 0

    def summary(self) -> str:
        """One line for a report."""
        return (
            f"{self.line_code} {self.earlier_year} to {self.later_year}: "
            f"{len(self.compared)} posts read in both years, "
            f"{len(self.lost)} lost criterion, {len(self.gained)} gained it, "
            f"net {self.net:+d}"
        )


def best_by_year(
    readings: list[Reading],
    *,
    lead: LeadKind = LeadKind.PIPE,
) -> dict[tuple[str, int], YearReading]:
    """The most protected off reading each post managed in each year.

    The best rather than the last, because a post read twice in a year was
    usually read again to check a bad number, and the follow up is the one that
    describes the pipe once somebody had looked at it.
    """
    found: dict[tuple[str, int], YearReading] = {}
    for reading in readings:
        if reading.lead is not lead:
            continue
        value = reading.off_cse_mv
        if value is None:
            continue
        key = (reading.test_point_code, reading.taken_on.year)
        current = found.get(key)
        if current is None or value < current.off_mv:
            found[key] = YearReading(
                test_point_code=reading.test_point_code,
                year=reading.taken_on.year,
                off_mv=value,
            )
    return found


def compare_years(
    line_code: str,
    readings: list[Reading],
    *,
    earlier_year: int,
    later_year: int,
    threshold_mv: float = DEFAULT_PROTECTION_MV,
    lead: LeadKind = LeadKind.PIPE,
) -> YearOnYear:
    """Compare two years of one line, post by post."""
    if later_year <= earlier_year:
        raise ValidationError(
            "the later year has to come after the earlier one",
            earlier_year=earlier_year,
            later_year=later_year,
        )
    best = best_by_year(readings, lead=lead)
    earlier = {code: item for (code, year), item in best.items() if year == earlier_year}
    later = {code: item for (code, year), item in best.items() if year == later_year}
    both = sorted(set(earlier) & set(later))
    lost: list[Change] = []
    gained: list[Change] = []
    held: list[str] = []
    for code in both:
        was = earlier[code]
        now = later[code]
        if was.meets(threshold_mv) and not now.meets(threshold_mv):
            lost.append(Change(code, was.off_mv, now.off_mv))
        elif not was.meets(threshold_mv) and now.meets(threshold_mv):
            gained.append(Change(code, was.off_mv, now.off_mv))
        else:
            held.append(code)
    return YearOnYear(
        line_code=line_code,
        earlier_year=earlier_year,
        later_year=later_year,
        threshold_mv=threshold_mv,
        compared=tuple(both),
        lost=tuple(sorted(lost, key=lambda item: -item.movement_mv)),
        gained=tuple(sorted(gained, key=lambda item: item.movement_mv)),
        held=tuple(held),
        only_earlier=tuple(sorted(set(earlier) - set(later))),
        only_later=tuple(sorted(set(later) - set(earlier))),
    )


def years_present(readings: list[Reading], *, lead: LeadKind = LeadKind.PIPE) -> list[int]:
    """Every year the readings cover, oldest first."""
    return sorted({year for _, year in best_by_year(readings, lead=lead)})


def latest_pair(
    readings: list[Reading], *, lead: LeadKind = LeadKind.PIPE
) -> tuple[int, int] | None:
    """The two most recent years with readings in them."""
    years = years_present(readings, lead=lead)
    if len(years) < 2:
        return None
    return (years[-2], years[-1])


def as_of_year(readings: list[Reading], year: int) -> list[Reading]:
    """Only the readings taken in one year."""
    return [reading for reading in readings if reading.taken_on.year == year]


def first_year(readings: list[Reading]) -> int | None:
    """The earliest year anything was read."""
    years = sorted({reading.taken_on.year for reading in readings})
    return years[0] if years else None
