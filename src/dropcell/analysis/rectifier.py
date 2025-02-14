"""Reading a rectifier's history rather than its last check sheet.

A single check says the unit was putting out twelve amps at eighteen volts on a
Tuesday. That is almost no information. The same unit's last six checks say
whether the output is falling, whether the circuit resistance is climbing,
whether somebody has been winding the taps up to hold the output, and whether
the hour meter has been running between visits.

The last of those is the one that catches the failure nobody sees. A unit that
trips at night and resets in the morning reads perfectly on every visit and
spends half its life off. The hour meter is the only witness, and comparing it
against the elapsed time between two checks is the whole test.

The tap history is the second. A groundbed drying out shows up first as a
technician winding the coarse tap up a notch every visit to hold the same
output, and nobody writes that down as a problem because at every single visit
the output was fine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.rectifier import Rectifier, RectifierCheck

HOURS_PER_DAY = 24.0
RUNNING_SHARE_FLOOR = 0.9
OUTPUT_DROP_SHARE = 0.3
RESISTANCE_RISE_SHARE = 0.5


class UnitFault(StrEnum):
    """What a unit's history says is wrong with it."""

    DEAD = "dead"
    OUTPUT_FALLING = "output_falling"
    RESISTANCE_CLIMBING = "resistance_climbing"
    TAPS_CLIMBING = "taps_climbing"
    NOT_RUNNING = "not_running"
    AT_CAPACITY = "at_capacity"

    @property
    def is_urgent(self) -> bool:
        """Whether this one needs somebody this month rather than this year."""
        return self in {UnitFault.DEAD, UnitFault.NOT_RUNNING}


@dataclass(frozen=True)
class UnitAssessment:
    """What a unit's checks add up to."""

    tag: str
    checks: int
    latest: RectifierCheck | None
    faults: tuple[UnitFault, ...]
    notes: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        """Whether nothing was found."""
        return not self.faults

    @property
    def urgent(self) -> bool:
        """Whether anything found needs attention soon."""
        return any(fault.is_urgent for fault in self.faults)

    def render(self) -> str:
        """One line and its reasons."""
        if self.healthy:
            return f"{self.tag}: nothing found over {self.checks} checks"
        return f"{self.tag}: " + ", ".join(str(fault) for fault in self.faults)


def running_share(earlier: RectifierCheck, later: RectifierCheck) -> float | None:
    """The share of the interval the unit was actually energised."""
    if earlier.hour_meter is None or later.hour_meter is None:
        return None
    days = (later.checked_on - earlier.checked_on).days
    if days <= 0:
        return None
    elapsed = days * HOURS_PER_DAY
    ran = later.hour_meter - earlier.hour_meter
    if ran < 0:
        raise ValidationError(
            "an hour meter does not run backwards",
            tag=later.rectifier_tag,
            earlier=earlier.hour_meter,
            later=later.hour_meter,
        )
    return ran / elapsed


def assess_unit(
    unit: Rectifier,
    checks: list[RectifierCheck],
    *,
    window: int = 6,
) -> UnitAssessment:
    """Read one unit's recent history."""
    if window < 2:
        raise ValidationError("a history needs at least two checks", window=window)
    ordered = sorted(checks, key=lambda check: check.checked_on)[-window:]
    if not ordered:
        return UnitAssessment(
            tag=unit.tag, checks=0, latest=None, faults=(), notes=("never checked",)
        )
    latest = ordered[-1]
    faults: list[UnitFault] = []
    notes: list[str] = []
    if latest.is_off:
        faults.append(UnitFault.DEAD)
        notes.append(f"putting out {latest.output_current_a:.2f} A on the last visit")
    if latest.is_near_capacity(unit):
        faults.append(UnitFault.AT_CAPACITY)
        notes.append(
            f"{latest.load_fraction(unit):.0%} of a {unit.rated_current_a:.0f} A nameplate"
        )
    if len(ordered) >= 2:
        first = ordered[0]
        if first.output_current_a > 0 and not latest.is_off:
            fall = (first.output_current_a - latest.output_current_a) / first.output_current_a
            if fall >= OUTPUT_DROP_SHARE:
                faults.append(UnitFault.OUTPUT_FALLING)
                notes.append(f"output down {fall:.0%} since {first.checked_on.isoformat()}")
        early_resistance = first.circuit_resistance_ohm
        late_resistance = latest.circuit_resistance_ohm
        if early_resistance and late_resistance:
            rise = (late_resistance - early_resistance) / early_resistance
            if rise >= RESISTANCE_RISE_SHARE:
                faults.append(UnitFault.RESISTANCE_CLIMBING)
                notes.append(
                    f"circuit resistance up {rise:.0%}, "
                    f"{early_resistance:.2f} to {late_resistance:.2f} ohm"
                )
        if _taps_climbing(ordered):
            faults.append(UnitFault.TAPS_CLIMBING)
            notes.append("the taps have been wound up at every visit")
        share = _worst_running_share(ordered)
        if share is not None and share < RUNNING_SHARE_FLOOR:
            faults.append(UnitFault.NOT_RUNNING)
            notes.append(f"the hour meter says it ran {share:.0%} of one interval")
    return UnitAssessment(
        tag=unit.tag,
        checks=len(ordered),
        latest=latest,
        faults=tuple(faults),
        notes=tuple(notes),
    )


def _taps_climbing(ordered: list[RectifierCheck]) -> bool:
    if len(ordered) < 3:
        return False
    positions = [(check.coarse_tap, check.fine_tap) for check in ordered]
    rises = 0
    for earlier, later in zip(positions, positions[1:], strict=False):
        if later < earlier:
            return False
        if later > earlier:
            rises += 1
    return rises >= len(positions) - 1


def _worst_running_share(ordered: list[RectifierCheck]) -> float | None:
    shares = []
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        share = running_share(earlier, later)
        if share is not None:
            shares.append(share)
    return min(shares) if shares else None


def urgent_first(assessments: list[UnitAssessment]) -> list[UnitAssessment]:
    """Order units by how badly they need somebody."""
    return sorted(
        assessments,
        key=lambda item: (not item.urgent, item.healthy, item.tag),
    )
