"""AC interference, which corrodes pipe that every DC criterion says is fine.

A pipeline sharing a corridor with a high voltage overhead line picks up an
induced AC voltage. The DC protection is untouched and every potential criterion
passes, and the steel at a small coating holiday still goes at a rate that can
take a wall out in a few years. The mechanism needs a small defect rather than a
large one, because what matters is current density and a pinhole concentrates
everything it collects.

Density is what is judged, not voltage. The same four volts on the pipe is
harmless in dry sand and destructive in wet clay, because the soil resistivity
decides how much current that voltage can push through a given hole. A standard
one square centimetre coupon stands in for the hole so the numbers from two
different sites can be compared.

Touch voltage is a separate matter with the same cause. It is a safety limit on
what somebody handling an exposed appurtenance can be exposed to, and it has
nothing to do with whether the pipe is corroding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dropcell.criteria.base import Assessment, Criterion, Evidence, Outcome, not_assessed
from dropcell.errors import ValidationError

STANDARD_COUPON_AREA_M2 = 1e-4
AC_DENSITY_LOW_RISK = 30.0
AC_DENSITY_HIGH_RISK = 100.0
TOUCH_VOLTAGE_LIMIT_V = 15.0
AC_TO_DC_RATIO_LIMIT = 5.0
DC_DENSITY_FLOOR_A_PER_M2 = 1.0


def equivalent_diameter_m(area_m2: float) -> float:
    """Diameter of a round holiday with that area."""
    if area_m2 <= 0:
        raise ValidationError("holiday area must be positive", area_m2=area_m2)
    return 2.0 * math.sqrt(area_m2 / math.pi)


def ac_current_density(
    ac_voltage_v: float,
    resistivity_ohm_m: float,
    *,
    area_m2: float = STANDARD_COUPON_AREA_M2,
) -> float:
    """AC current density at a small round coating defect."""
    if ac_voltage_v < 0:
        raise ValidationError("AC voltage cannot be negative", ac_voltage_v=ac_voltage_v)
    if resistivity_ohm_m <= 0:
        raise ValidationError("resistivity must be positive", value=resistivity_ohm_m)
    diameter = equivalent_diameter_m(area_m2)
    return 8.0 * ac_voltage_v / (resistivity_ohm_m * math.pi * diameter)


@dataclass(frozen=True)
class AcCorrosionLimit(Criterion):
    """AC current density against the band where corrosion is expected."""

    high_risk_a_per_m2: float = AC_DENSITY_HIGH_RISK
    low_risk_a_per_m2: float = AC_DENSITY_LOW_RISK
    key: str = "ac_current_density"
    label: str = "AC current density at a standard coupon"

    def density_for(self, evidence: Evidence) -> float | None:
        """The measured density, or one worked out from voltage and resistivity."""
        if evidence.ac_current_density_a_per_m2 is not None:
            return evidence.ac_current_density_a_per_m2
        if evidence.ac_voltage_v is None:
            return None
        resistivity = evidence.soil_resistivity_ohm_m or evidence.segment.soil_resistivity_ohm_m
        if resistivity is None:
            return None
        return ac_current_density(evidence.ac_voltage_v, resistivity)

    def applies_to(self, evidence: Evidence) -> bool:
        """Only where somebody has measured the AC side at all."""
        return self.density_for(evidence) is not None

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge one point on its AC current density."""
        density = self.density_for(evidence)
        if density is None:
            return not_assessed(self.key, ["ac_current_density_a_per_m2"])
        if density >= self.high_risk_a_per_m2:
            outcome = Outcome.EXCEEDED
            note = "AC corrosion expected at this density"
        elif density >= self.low_risk_a_per_m2:
            outcome = Outcome.NOT_MET
            note = "AC corrosion possible, mitigation should be considered"
        else:
            outcome = Outcome.MET
            note = ""
        return Assessment(
            criterion=self.key,
            outcome=outcome,
            margin_mv=None,
            note=note,
            detail={
                "ac_current_density_a_per_m2": density,
                "low_risk_a_per_m2": self.low_risk_a_per_m2,
                "high_risk_a_per_m2": self.high_risk_a_per_m2,
            },
        )


@dataclass(frozen=True)
class AcToDcRatioLimit(Criterion):
    """AC density against DC density, which matters once the DC is high enough.

    A large DC current density keeps the steel surface in a state where the AC
    does more damage, so the ratio is only read as a warning where the DC side
    is already substantial. Below that floor a high ratio is arithmetic rather
    than a finding.
    """

    ratio_limit: float = AC_TO_DC_RATIO_LIMIT
    dc_floor_a_per_m2: float = DC_DENSITY_FLOOR_A_PER_M2
    key: str = "ac_to_dc_ratio"
    label: str = "AC current density against DC current density"

    def applies_to(self, evidence: Evidence) -> bool:
        """Needs both densities, and a DC side worth comparing against."""
        dc = evidence.dc_current_density_a_per_m2
        return (
            evidence.ac_current_density_a_per_m2 is not None
            and dc is not None
            and dc >= self.dc_floor_a_per_m2
        )

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge the ratio of the two densities."""
        missing = evidence.missing("ac_current_density_a_per_m2", "dc_current_density_a_per_m2")
        if missing:
            return not_assessed(self.key, missing)
        ac = evidence.ac_current_density_a_per_m2
        dc = evidence.dc_current_density_a_per_m2
        assert ac is not None
        assert dc is not None
        if dc < self.dc_floor_a_per_m2:
            return Assessment(
                criterion=self.key,
                outcome=Outcome.NOT_ASSESSED,
                note="the DC side is too small for the ratio to mean anything",
                detail={
                    "dc_current_density_a_per_m2": dc,
                    "dc_floor_a_per_m2": self.dc_floor_a_per_m2,
                },
            )
        ratio = ac / dc
        exceeded = ratio > self.ratio_limit
        return Assessment(
            criterion=self.key,
            outcome=Outcome.EXCEEDED if exceeded else Outcome.MET,
            margin_mv=None,
            note="AC dominates the DC at this point" if exceeded else "",
            detail={"ratio": ratio, "ratio_limit": self.ratio_limit},
        )


@dataclass(frozen=True)
class TouchVoltageLimit(Criterion):
    """A safety limit on the AC a person can be exposed to at an appurtenance."""

    limit_v: float = TOUCH_VOLTAGE_LIMIT_V
    key: str = "touch_voltage"
    label: str = "AC voltage against the touch limit"

    def applies_to(self, evidence: Evidence) -> bool:
        """Only where an AC voltage was read."""
        return evidence.ac_voltage_v is not None

    def assess(self, evidence: Evidence) -> Assessment:
        """Judge the AC voltage against the safety limit."""
        missing = evidence.missing("ac_voltage_v")
        if missing:
            return not_assessed(self.key, missing)
        voltage = evidence.ac_voltage_v
        assert voltage is not None
        exceeded = voltage > self.limit_v
        return Assessment(
            criterion=self.key,
            outcome=Outcome.EXCEEDED if exceeded else Outcome.MET,
            margin_mv=None,
            note="above the touch voltage limit" if exceeded else "",
            detail={"ac_voltage_v": voltage, "limit_v": self.limit_v},
        )
