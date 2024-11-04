"""Judging a coupon, which is the one place every criterion can run at once.

A coupon reading carries an IR free potential, a DC current density and an AC
current density, all measured rather than inferred. That is the full set of
evidence, so a coupon is the only point on a line where the potential criteria
and the AC limits can be applied to the same measurement at the same moment
without anybody having to assume anything.

It is also where the two disagree most usefully. A coupon can sit comfortably
past the polarised threshold while drawing an AC density that will take the
steel out in five years, and a report that prints only the potential will say
that spot is fine right up until it leaks.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dropcell.criteria.base import Evidence
from dropcell.criteria.evaluate import CriterionSet, PointVerdict
from dropcell.criteria.registry import AC_INTERFERENCE, IMPRESSED_CURRENT
from dropcell.model.coupon import Coupon, CouponReading
from dropcell.model.segment import Segment


@dataclass(frozen=True)
class CouponAssessment:
    """What one coupon reading came to."""

    coupon: Coupon
    reading: CouponReading
    verdict: PointVerdict
    dc_density_a_per_m2: float | None
    ac_density_a_per_m2: float | None

    @property
    def code(self) -> str:
        """The coupon's code."""
        return self.coupon.code

    @property
    def taken_on(self) -> dt.date:
        """When the reading was taken."""
        return self.reading.taken_on

    @property
    def ac_to_dc_ratio(self) -> float | None:
        """How far the AC side dominates the DC side."""
        if self.ac_density_a_per_m2 is None or not self.dc_density_a_per_m2:
            return None
        return self.ac_density_a_per_m2 / self.dc_density_a_per_m2

    @property
    def protected(self) -> bool:
        """Whether a potential criterion was met."""
        return self.verdict.protected

    @property
    def has_findings(self) -> bool:
        """Whether anything here belongs on the exception register."""
        return self.verdict.has_findings

    @property
    def looks_fine_on_potential_alone(self) -> bool:
        """Whether a potential only report would call this spot healthy.

        This is the trap the coupon exists to catch. It is true exactly when a
        criterion was met and a limit was still broken, which is the case a
        report that prints one number per post cannot show at all.
        """
        return self.protected and bool(self.verdict.exceeded)


def build_evidence(
    coupon: Coupon,
    reading: CouponReading,
    segment: Segment,
) -> Evidence:
    """Turn a coupon reading into the evidence a criterion set wants."""
    dc_density = (
        None if reading.dc_shunt_mv is None else coupon.density_a_per_m2(reading.dc_shunt_mv)
    )
    ac_density = (
        None if reading.ac_shunt_mv is None else coupon.density_a_per_m2(reading.ac_shunt_mv)
    )
    return Evidence(
        segment=segment,
        on_mv=reading.on_mv,
        off_mv=reading.disconnected_mv,
        ac_voltage_v=reading.ac_voltage_v,
        ac_current_density_a_per_m2=ac_density,
        dc_current_density_a_per_m2=dc_density,
        soil_resistivity_ohm_m=segment.soil_resistivity_ohm_m,
        interrupted=reading.is_ir_free,
        label=coupon.code,
    )


def assess_coupon(
    coupon: Coupon,
    reading: CouponReading,
    segment: Segment,
    *,
    criterion_set: CriterionSet | None = None,
) -> CouponAssessment:
    """Run a criterion set against one coupon reading.

    The AC set is the default because a coupon that carries an AC measurement
    and is judged without the AC limits has thrown away the one thing it was
    installed for.
    """
    evidence = build_evidence(coupon, reading, segment)
    chosen = criterion_set
    if chosen is None:
        carries_ac = (
            evidence.ac_current_density_a_per_m2 is not None
            or evidence.ac_voltage_v is not None
        )
        chosen = AC_INTERFERENCE if carries_ac else IMPRESSED_CURRENT
    return CouponAssessment(
        coupon=coupon,
        reading=reading,
        verdict=chosen.evaluate(evidence),
        dc_density_a_per_m2=evidence.dc_current_density_a_per_m2,
        ac_density_a_per_m2=evidence.ac_current_density_a_per_m2,
    )


def worst_first(assessments: list[CouponAssessment]) -> list[CouponAssessment]:
    """Order coupons by how much AC they are taking, worst first."""
    return sorted(
        assessments,
        key=lambda item: (
            -(item.ac_density_a_per_m2 or 0.0),
            item.code,
        ),
    )
