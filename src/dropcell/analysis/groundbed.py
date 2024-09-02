"""How much of a groundbed has been spent, from the checks that were taken.

Anode consumption depends on ampere hours, and nobody measures ampere hours.
What exists is a handful of current readings a year, taken by somebody who
drove out, read a panel meter, and drove away. Turning those into a total is
integration over a very coarse sample, and the honest way to do it is to assume
the output moved linearly between one reading and the next.

That assumption is wrong in a specific direction and it is worth knowing which.
A unit that fails between two visits reads full output in January and zero in
March, and the trapezoid credits it with half output for two months it spent
dead. So the number produced here overstates consumption on a bed whose unit has
been failing, which is the safe direction to be wrong in: it retires a bed early
rather than leaving one in the ground past the end of it.

The tail matters as much as the middle. A bed whose last check was eighteen
months ago has been consuming anode that whole time, and stopping the
integration at the last reading is how a bed that is finished reads as half
spent.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.groundbed import Groundbed
from dropcell.model.rectifier import RectifierCheck

DAYS_PER_YEAR = 365.25


def amp_years(checks: list[RectifierCheck], *, until: dt.date) -> float:
    """Integrate the current a bed has passed, from the checks and the tail."""
    if not checks:
        return 0.0
    ordered = sorted(checks, key=lambda check: check.checked_on)
    if ordered[-1].checked_on > until:
        raise ValidationError(
            "a check cannot sit after the date being worked to",
            until=until.isoformat(),
            last_check=ordered[-1].checked_on.isoformat(),
        )
    total = 0.0
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        days = (later.checked_on - earlier.checked_on).days
        mean = (earlier.output_current_a + later.output_current_a) / 2.0
        total += mean * days / DAYS_PER_YEAR
    tail_days = (until - ordered[-1].checked_on).days
    total += ordered[-1].output_current_a * tail_days / DAYS_PER_YEAR
    return total


@dataclass(frozen=True)
class BedStatus:
    """What the checks say about one bed."""

    groundbed_code: str
    as_of: dt.date
    amp_years: float
    consumed_kg: float
    remaining_kg: float
    spent_fraction: float
    present_current_a: float
    remaining_life_years: float | None
    end_of_life: bool

    @property
    def projected_end(self) -> dt.date | None:
        """When the bed runs out at the output it is passing now."""
        if self.remaining_life_years is None:
            return None
        return self.as_of + dt.timedelta(days=self.remaining_life_years * DAYS_PER_YEAR)

    @property
    def spent_percent(self) -> float:
        """The spent fraction as a percentage, for a report."""
        return 100.0 * self.spent_fraction


def assess_bed(
    bed: Groundbed,
    checks: list[RectifierCheck],
    *,
    as_of: dt.date,
) -> BedStatus:
    """Work out where one bed has got to."""
    passed = amp_years(checks, until=as_of)
    present = 0.0
    if checks:
        present = max(checks, key=lambda check: check.checked_on).output_current_a
    remaining_life: float | None = None
    if present > 0:
        remaining_life = bed.remaining_life_years(passed, present)
    return BedStatus(
        groundbed_code=bed.code,
        as_of=as_of,
        amp_years=passed,
        consumed_kg=bed.consumption_kg(passed),
        remaining_kg=bed.remaining_mass_kg(passed),
        spent_fraction=bed.spent_fraction(passed),
        present_current_a=present,
        remaining_life_years=remaining_life,
        end_of_life=bed.is_end_of_life(passed),
    )


def rank_beds(statuses: list[BedStatus]) -> list[BedStatus]:
    """Order beds by how close they are to being finished, worst first."""
    return sorted(statuses, key=lambda status: (-status.spent_fraction, status.groundbed_code))


def beds_due_within(statuses: list[BedStatus], years: float) -> list[BedStatus]:
    """Beds that run out inside a planning horizon."""
    if years < 0:
        raise ValidationError("a horizon cannot run backwards", years=years)
    found: list[BedStatus] = []
    for status in statuses:
        if status.end_of_life:
            found.append(status)
            continue
        if status.remaining_life_years is not None and status.remaining_life_years <= years:
            found.append(status)
    return found
