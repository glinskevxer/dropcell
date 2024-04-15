"""Groundbeds, and the arithmetic of watching anodes dissolve.

A groundbed is the positive end of the circuit. Current leaving an anode takes
metal with it, at a rate that depends only on what the anode is made of, so a
bed's life is a mass divided by a consumption rate times a current. That is the
one number in cathodic protection that can be forecast honestly years ahead,
and it is the number nobody looks at until the rectifier runs out of tap.

Not all of the mass is usable. Anodes wear unevenly, the ends go first, and a
bed is treated as finished once a fixed fraction of the metal is gone even
though there is still some left in the hole.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.errors import ValidationError
from dropcell.model.enums import AnodeMaterial, GroundbedKind
from dropcell.model.ids import normalise_code

DEFAULT_UTILISATION = 0.85
END_OF_LIFE_FRACTION = 0.9


@dataclass(frozen=True)
class Groundbed:
    """One bed of anodes."""

    code: str
    kind: GroundbedKind
    material: AnodeMaterial
    anode_count: int
    anode_mass_kg: float
    installed_on: dt.date
    design_current_a: float
    utilisation: float = DEFAULT_UTILISATION
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="groundbed code"))
        if self.anode_count < 1:
            raise ValidationError("a bed needs at least one anode", code=self.code)
        if self.anode_mass_kg <= 0:
            raise ValidationError("anode mass must be positive", code=self.code)
        if self.design_current_a <= 0:
            raise ValidationError("design current must be positive", code=self.code)
        if not 0 < self.utilisation <= 1:
            raise ValidationError(
                "utilisation is a fraction of the anode mass",
                code=self.code,
                utilisation=self.utilisation,
            )
        if self.kind is GroundbedKind.GALVANIC_STRING and not self.material.is_galvanic:
            raise ValidationError(
                "a galvanic string cannot be built from an impressed current anode",
                code=self.code,
                material=str(self.material),
            )

    @property
    def installed_mass_kg(self) -> float:
        """All the metal that went in the hole."""
        return self.anode_count * self.anode_mass_kg

    @property
    def usable_mass_kg(self) -> float:
        """The part of that metal the bed can actually spend."""
        return self.installed_mass_kg * self.utilisation

    @property
    def is_galvanic(self) -> bool:
        """Whether the bed drives itself."""
        return self.material.is_galvanic

    def consumption_kg(self, amp_years: float) -> float:
        """Metal lost after passing that many ampere years."""
        if amp_years < 0:
            raise ValidationError("ampere years cannot be negative", code=self.code)
        return amp_years * self.material.consumption_kg_per_amp_year

    def remaining_mass_kg(self, amp_years: float) -> float:
        """Usable metal still in the ground, floored at nothing left."""
        return max(0.0, self.usable_mass_kg - self.consumption_kg(amp_years))

    def spent_fraction(self, amp_years: float) -> float:
        """How much of the usable mass has gone, capped at all of it."""
        return min(1.0, self.consumption_kg(amp_years) / self.usable_mass_kg)

    def design_life_years(self) -> float:
        """Life the bed was sized for, at its design current."""
        return self.usable_mass_kg / (
            self.design_current_a * self.material.consumption_kg_per_amp_year
        )

    def remaining_life_years(self, amp_years: float, current_a: float) -> float:
        """Years left at a given output, given what the bed has already passed."""
        if current_a <= 0:
            raise ValidationError("current must be positive", code=self.code)
        remaining = self.remaining_mass_kg(amp_years)
        return remaining / (current_a * self.material.consumption_kg_per_amp_year)

    def is_end_of_life(self, amp_years: float) -> bool:
        """Whether the bed has spent enough of itself to need replacing."""
        return self.spent_fraction(amp_years) >= END_OF_LIFE_FRACTION
