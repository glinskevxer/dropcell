"""Depolarisation surveys, which take the whole line out of protection for a day.

Every rectifier on the system is switched off together and left off. The
instant off potential is read at each post as the current stops, and then the
line is left to drift back towards its native state while somebody drives round
reading the same posts again several hours later.

It is the most disruptive thing a CP department does. The line is unprotected
for the duration, the work has to be booked with operations, and a survey that
goes wrong cannot be repeated the following week. So the checks on whether the
survey was valid matter as much as the readings.

Two of those checks are worth stating. The off readings all have to come from
the same switch off, or the decays are measured from different starting points
and mean nothing together. And the drift period has to be long enough that what
is being measured is polarisation rather than the tail of the IR drop, which is
why a survey read two hours after switch off and one read at twenty four hours
are not comparable and should not be averaged into the same figure.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.criteria.decay import MINIMUM_DECAY_MV, MINIMUM_DEPOLARISATION_HOURS
from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.model.reading import check_potential

FULL_DEPOLARISATION_HOURS = 24.0


@dataclass(frozen=True)
class DepolarisationPoint:
    """One post, read twice, either side of the drift."""

    test_point_code: str
    off_mv: float
    depolarised_mv: float | None = None
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "test_point_code",
            normalise_code(self.test_point_code, kind="test point code"),
        )
        check_potential(self.off_mv, "instant off potential")
        if self.depolarised_mv is not None:
            check_potential(self.depolarised_mv, "depolarised potential")

    @property
    def decay_mv(self) -> float | None:
        """How far the post drifted back once the current stopped."""
        if self.depolarised_mv is None:
            return None
        return self.depolarised_mv - self.off_mv

    @property
    def read_twice(self) -> bool:
        """Whether somebody came back for the second reading."""
        return self.depolarised_mv is not None

    def meets(self, minimum_mv: float = MINIMUM_DECAY_MV) -> bool | None:
        """Whether the drift satisfies the decay criterion."""
        decay = self.decay_mv
        return None if decay is None else decay >= minimum_mv


@dataclass(frozen=True)
class DepolarisationSurvey:
    """One switch off, and everything read against it."""

    line_code: str
    switched_off_at: dt.datetime
    read_back_at: dt.datetime
    points: tuple[DepolarisationPoint, ...]
    technician: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if self.read_back_at <= self.switched_off_at:
            raise ValidationError(
                "the second pass has to come after the switch off",
                line_code=self.line_code,
            )
        if not self.points:
            raise ValidationError("a survey with no posts read is not a survey")
        seen: set[str] = set()
        for point in self.points:
            if point.test_point_code in seen:
                raise ValidationError(
                    "the same post appears twice in one survey",
                    test_point_code=point.test_point_code,
                )
            seen.add(point.test_point_code)

    @property
    def hours_off(self) -> float:
        """How long the line was left out of protection."""
        return (self.read_back_at - self.switched_off_at).total_seconds() / 3600.0

    @property
    def long_enough(self) -> bool:
        """Whether the drift period is long enough for the readings to be decay."""
        return self.hours_off >= MINIMUM_DEPOLARISATION_HOURS

    @property
    def fully_depolarised(self) -> bool:
        """Whether the line was left off for the full period the trade quotes."""
        return self.hours_off >= FULL_DEPOLARISATION_HOURS

    @property
    def read_back(self) -> tuple[DepolarisationPoint, ...]:
        """Only the posts somebody came back to."""
        return tuple(point for point in self.points if point.read_twice)

    @property
    def missed_on_the_second_pass(self) -> tuple[str, ...]:
        """Posts read on the way out and not on the way back."""
        return tuple(point.test_point_code for point in self.points if not point.read_twice)

    def meeting(self, minimum_mv: float = MINIMUM_DECAY_MV) -> tuple[DepolarisationPoint, ...]:
        """Posts whose drift satisfies the criterion."""
        return tuple(point for point in self.read_back if point.meets(minimum_mv))

    def failing(self, minimum_mv: float = MINIMUM_DECAY_MV) -> tuple[DepolarisationPoint, ...]:
        """Posts read twice whose drift does not satisfy the criterion."""
        return tuple(point for point in self.read_back if point.meets(minimum_mv) is False)

    def share_meeting(self, minimum_mv: float = MINIMUM_DECAY_MV) -> float:
        """The share of posts read twice that satisfied the criterion."""
        if not self.read_back:
            return 0.0
        return len(self.meeting(minimum_mv)) / len(self.read_back)

    def problems(self) -> tuple[str, ...]:
        """Everything about this survey that stops it counting as evidence."""
        said: list[str] = []
        if not self.long_enough:
            said.append(
                f"only {self.hours_off:.1f} hours off, which is not long enough to be decay"
            )
        elif not self.fully_depolarised:
            said.append(f"{self.hours_off:.1f} hours off, short of the full period")
        missed = self.missed_on_the_second_pass
        if missed:
            said.append(f"{len(missed)} posts were not read on the second pass")
        return tuple(said)
