"""Dynamic stray current, where the pipe potential will not sit still.

Near a DC traction system the potential of a buried pipe swings by hundreds of
millivolts on the timetable of the trains. A technician who arrives at eleven in
the morning, reads minus nine hundred and drives away has recorded a true fact
about eleven in the morning and nothing at all about the pipe. The only way to
say anything is to leave a logger on the post for a day and read the
distribution rather than a number.

What matters is not the average. A pipe that averages a comfortable potential
while spending two hours a day discharging is corroding for those two hours, and
the average hides exactly the part that does the damage. So the questions asked
of a log are about time above a threshold, about the longest single excursion,
and about the total swing, all of which a mean throws away.
"""

from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass

from dropcell.criteria.potential import DEFAULT_PROTECTION_MV
from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code

DYNAMIC_SWING_MV = 100.0


@dataclass(frozen=True)
class StrayCurrentLog:
    """One logger left on one post for a while."""

    test_point_code: str
    started_at: dt.datetime
    sample_interval_s: float
    samples_mv: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "test_point_code",
            normalise_code(self.test_point_code, kind="test point code"),
        )
        if self.sample_interval_s <= 0:
            raise ValidationError(
                "the sample interval must be positive",
                sample_interval_s=self.sample_interval_s,
            )
        if len(self.samples_mv) < 2:
            raise ValidationError(
                "a log needs more than one sample", count=len(self.samples_mv)
            )

    @property
    def count(self) -> int:
        """How many samples the logger took."""
        return len(self.samples_mv)

    @property
    def duration_s(self) -> float:
        """How long the logger was on the post."""
        return (self.count - 1) * self.sample_interval_s

    @property
    def finished_at(self) -> dt.datetime:
        """When the last sample was taken."""
        return self.started_at + dt.timedelta(seconds=self.duration_s)

    @property
    def mean_mv(self) -> float:
        """The average potential over the log, which hides the excursions."""
        return statistics.fmean(self.samples_mv)

    @property
    def median_mv(self) -> float:
        """The middle potential, which the trains move less than the mean."""
        return statistics.median(self.samples_mv)

    @property
    def most_positive_mv(self) -> float:
        """The least protected moment in the log."""
        return max(self.samples_mv)

    @property
    def most_negative_mv(self) -> float:
        """The most protected moment in the log."""
        return min(self.samples_mv)

    @property
    def swing_mv(self) -> float:
        """How far the potential moved from end to end."""
        return self.most_positive_mv - self.most_negative_mv

    def percentile_mv(self, share: float) -> float:
        """The potential that this share of the samples sit below."""
        if not 0.0 <= share <= 1.0:
            raise ValidationError("a percentile is a share between nought and one", share=share)
        ordered = sorted(self.samples_mv)
        position = share * (len(ordered) - 1)
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        weight = position - low
        return ordered[low] * (1.0 - weight) + ordered[high] * weight

    def samples_above(self, threshold_mv: float = DEFAULT_PROTECTION_MV) -> int:
        """How many samples sat less negative than the threshold."""
        return sum(1 for value in self.samples_mv if value > threshold_mv)

    def share_above(self, threshold_mv: float = DEFAULT_PROTECTION_MV) -> float:
        """What share of the log sat less negative than the threshold."""
        return self.samples_above(threshold_mv) / self.count

    def seconds_above(self, threshold_mv: float = DEFAULT_PROTECTION_MV) -> float:
        """How long the pipe spent less negative than the threshold."""
        return self.samples_above(threshold_mv) * self.sample_interval_s

    def longest_excursion_s(self, threshold_mv: float = DEFAULT_PROTECTION_MV) -> float:
        """The longest single stretch above the threshold, which is what corrodes."""
        longest = 0
        run = 0
        for value in self.samples_mv:
            if value > threshold_mv:
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        return longest * self.sample_interval_s

    def is_dynamic(self, *, swing_limit_mv: float = DYNAMIC_SWING_MV) -> bool:
        """Whether the potential moves enough to call this stray current."""
        return self.swing_mv > swing_limit_mv


@dataclass(frozen=True)
class StraySummary:
    """The numbers a report carries about one logged post."""

    test_point_code: str
    started_at: dt.datetime
    duration_s: float
    mean_mv: float
    median_mv: float
    most_positive_mv: float
    most_negative_mv: float
    swing_mv: float
    share_above: float
    longest_excursion_s: float
    dynamic: bool


def summarise(
    log: StrayCurrentLog,
    *,
    threshold_mv: float = DEFAULT_PROTECTION_MV,
    swing_limit_mv: float = DYNAMIC_SWING_MV,
) -> StraySummary:
    """Reduce a whole log to the handful of figures a report can carry."""
    return StraySummary(
        test_point_code=log.test_point_code,
        started_at=log.started_at,
        duration_s=log.duration_s,
        mean_mv=log.mean_mv,
        median_mv=log.median_mv,
        most_positive_mv=log.most_positive_mv,
        most_negative_mv=log.most_negative_mv,
        swing_mv=log.swing_mv,
        share_above=log.share_above(threshold_mv),
        longest_excursion_s=log.longest_excursion_s(threshold_mv),
        dynamic=log.is_dynamic(swing_limit_mv=swing_limit_mv),
    )
