"""Coupons, which are a coating holiday somebody made on purpose.

A coupon is a small disc of the same steel as the pipe, buried beside it at the
same depth, wired back up to a test post through a shunt. It stands in for a
defect in the coating: a known area of bare metal, connected to the pipe, sitting
in the same soil.

It answers two questions no potential at a post can. The current the coupon
draws is measured directly across the shunt, so current density is a
measurement rather than an estimate. And the coupon can be disconnected on its
own, which gives a genuinely IR free potential without interrupting anything,
which is the only way to get one on a line that cannot be switched off.

The area is the whole of the arithmetic and it has to be the wetted area. A
coupon reported at one square centimetre that is actually exposed on both faces
gives a density that is out by a factor of two, in the direction that says
everything is fine.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.model.reading import check_potential

STANDARD_AREA_M2 = 1e-4


class CouponOrientation(StrEnum):
    """Which way the coupon faces, which decides what it represents."""

    TOP = "top"
    SIDE = "side"
    BOTTOM = "bottom"

    @property
    def represents_worst_case(self) -> bool:
        """Whether this face is where a real defect would be hardest to protect.

        Current reaches the top of a pipe first and the bottom last, so a
        coupon on the bottom is the pessimistic one. A programme that only ever
        installs top coupons is measuring the easy case and reporting it as the
        line.
        """
        return self is CouponOrientation.BOTTOM


@dataclass(frozen=True)
class Coupon:
    """One buried steel disc wired back to a post."""

    code: str
    test_point_code: str
    area_m2: float
    shunt_ohm: float
    installed_on: dt.date
    orientation: CouponOrientation = CouponOrientation.SIDE
    depth_m: float = 1.2
    description: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="coupon code"))
        object.__setattr__(
            self,
            "test_point_code",
            normalise_code(self.test_point_code, kind="test point code"),
        )
        if self.area_m2 <= 0:
            raise ValidationError("a coupon has to have some area", code=self.code)
        if self.shunt_ohm <= 0:
            raise ValidationError("a shunt has to have some resistance", code=self.code)
        if self.depth_m <= 0:
            raise ValidationError("a coupon is buried at some depth", code=self.code)

    @property
    def area_cm2(self) -> float:
        """The area in the unit the coupon was sold in."""
        return self.area_m2 * 1e4

    @property
    def is_standard_area(self) -> bool:
        """Whether this is the square centimetre coupon everything is compared at."""
        return abs(self.area_m2 - STANDARD_AREA_M2) < 1e-9

    def current_a(self, shunt_mv: float) -> float:
        """The current the coupon is drawing, from the drop across its shunt."""
        return (shunt_mv / 1000.0) / self.shunt_ohm

    def density_a_per_m2(self, shunt_mv: float) -> float:
        """Current density on the coupon, which is what the AC limits are set in."""
        return self.current_a(shunt_mv) / self.area_m2


@dataclass(frozen=True)
class CouponReading:
    """One visit to one coupon."""

    coupon_code: str
    taken_on: dt.date
    on_mv: float
    disconnected_mv: float | None = None
    dc_shunt_mv: float | None = None
    ac_shunt_mv: float | None = None
    ac_voltage_v: float | None = None
    technician: str = ""
    comment: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "coupon_code", normalise_code(self.coupon_code, kind="coupon code")
        )
        check_potential(self.on_mv, "coupon on potential")
        if self.disconnected_mv is not None:
            check_potential(self.disconnected_mv, "coupon disconnected potential")
        if self.ac_voltage_v is not None and self.ac_voltage_v < 0:
            raise ValidationError("AC voltage cannot be negative", coupon_code=self.coupon_code)

    @property
    def is_ir_free(self) -> bool:
        """Whether this visit caught a genuinely IR free potential."""
        return self.disconnected_mv is not None

    @property
    def ir_drop_mv(self) -> float | None:
        """How much of the connected reading was soil."""
        if self.disconnected_mv is None:
            return None
        return self.on_mv - self.disconnected_mv
