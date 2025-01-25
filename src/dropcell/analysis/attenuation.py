"""How far one drain point reaches, which decides where the next one goes.

Current fed onto a pipe at one place does not spread evenly. It leaks out
through the coating as it travels, so the potential shift falls off with
distance from the drain point, and it falls off exponentially rather than
linearly. Two constants decide how fast.

The first is the resistance of the steel itself along the line, which is fixed
by the wall thickness and nothing else. A thin walled distribution main is a
poor conductor and the current cannot get far along it.

The second is how well the coating holds the current in. A new epoxy line has
an enormous leakage resistance and one rectifier can protect thirty miles of
it. The same rectifier on the same steel with fifty year old tape wrap reaches a
mile, because the current is gone into the ground long before it gets anywhere.

That is the whole of the model and it is a crude one. It assumes a uniform
coating, uniform soil and an infinite line, and none of those is true. It is
used anyway because the question is where to put the next unit, the answer is
wanted to the nearest mile, and the alternative is a finite element model of a
pipeline whose coating condition nobody actually knows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.segment import Segment

STEEL_RESISTIVITY_OHM_M = 1.8e-7

COATING_RESISTANCE_OHM_M2: dict[str, float] = {
    "bare": 1.0,
    "coal_tar": 5_000.0,
    "asphalt": 3_000.0,
    "tape_wrap": 8_000.0,
    "fbe": 100_000.0,
    "three_layer_pe": 300_000.0,
    "liquid_epoxy": 50_000.0,
}


def steel_area_m2(outside_diameter_mm: float, wall_thickness_mm: float) -> float:
    """Cross section of the steel, which is what carries the current along."""
    if outside_diameter_mm <= 0 or wall_thickness_mm <= 0:
        raise ValidationError(
            "a pipe has an outside diameter and a wall",
            outside_diameter_mm=outside_diameter_mm,
            wall_thickness_mm=wall_thickness_mm,
        )
    if wall_thickness_mm >= outside_diameter_mm / 2:
        raise ValidationError("the wall has to fit inside the pipe")
    outer = outside_diameter_mm / 1000.0 / 2.0
    inner = outer - wall_thickness_mm / 1000.0
    return math.pi * (outer**2 - inner**2)


def longitudinal_resistance_ohm_per_m(
    outside_diameter_mm: float,
    wall_thickness_mm: float,
    *,
    resistivity_ohm_m: float = STEEL_RESISTIVITY_OHM_M,
) -> float:
    """Resistance of the steel per metre of line."""
    return resistivity_ohm_m / steel_area_m2(outside_diameter_mm, wall_thickness_mm)


def leakage_resistance_ohm_m(
    outside_diameter_mm: float,
    coating_resistance_ohm_m2: float,
) -> float:
    """Resistance to earth of one metre of coated pipe."""
    if coating_resistance_ohm_m2 <= 0:
        raise ValidationError(
            "coating resistance must be positive", value=coating_resistance_ohm_m2
        )
    circumference = math.pi * outside_diameter_mm / 1000.0
    return coating_resistance_ohm_m2 / circumference


def attenuation_constant(longitudinal: float, leakage: float) -> float:
    """How fast the shift falls off, per metre."""
    if longitudinal <= 0 or leakage <= 0:
        raise ValidationError(
            "both resistances have to be positive",
            longitudinal=longitudinal,
            leakage=leakage,
        )
    return math.sqrt(longitudinal / leakage)


def characteristic_resistance(longitudinal: float, leakage: float) -> float:
    """The resistance a drain point sees looking down an infinite line."""
    if longitudinal <= 0 or leakage <= 0:
        raise ValidationError("both resistances have to be positive")
    return math.sqrt(longitudinal * leakage)


@dataclass(frozen=True)
class Attenuation:
    """One segment's attenuation, worked from its own geometry and coating."""

    segment_code: str
    longitudinal_ohm_per_m: float
    leakage_ohm_m: float
    alpha_per_m: float
    characteristic_ohm: float

    @property
    def half_length_m(self) -> float:
        """How far the shift takes to halve."""
        return math.log(2.0) / self.alpha_per_m

    def shift_at(self, drain_shift_mv: float, distance_m: float) -> float:
        """The shift left after travelling that far from the drain point."""
        if distance_m < 0:
            raise ValidationError("distance cannot be negative", distance_m=distance_m)
        return drain_shift_mv * math.exp(-self.alpha_per_m * distance_m)

    def reach_m(self, drain_shift_mv: float, required_shift_mv: float) -> float:
        """How far the drain point protects, to a required shift."""
        if drain_shift_mv <= 0 or required_shift_mv <= 0:
            raise ValidationError("both shifts have to be positive")
        if required_shift_mv >= drain_shift_mv:
            return 0.0
        return math.log(drain_shift_mv / required_shift_mv) / self.alpha_per_m

    def spacing_m(self, drain_shift_mv: float, required_shift_mv: float) -> float:
        """How far apart drain points can sit, protecting both ways from each."""
        return 2.0 * self.reach_m(drain_shift_mv, required_shift_mv)


def for_segment(
    segment: Segment,
    *,
    coating_resistance_ohm_m2: float | None = None,
) -> Attenuation:
    """Work out a segment's attenuation from its geometry and its coating."""
    resistance = coating_resistance_ohm_m2
    if resistance is None:
        resistance = COATING_RESISTANCE_OHM_M2[str(segment.coating)]
    longitudinal = longitudinal_resistance_ohm_per_m(
        segment.outside_diameter_mm, segment.wall_thickness_mm
    )
    leakage = leakage_resistance_ohm_m(segment.outside_diameter_mm, resistance)
    return Attenuation(
        segment_code=segment.code,
        longitudinal_ohm_per_m=longitudinal,
        leakage_ohm_m=leakage,
        alpha_per_m=attenuation_constant(longitudinal, leakage),
        characteristic_ohm=characteristic_resistance(longitudinal, leakage),
    )
