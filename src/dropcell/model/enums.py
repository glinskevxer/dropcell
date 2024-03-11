"""Closed vocabularies shared by the whole package.

These are not free text fields with a helper. A coating type decides how much
current a segment is expected to draw and whether it can shield the pipe from
the very protection meant to save it; a test point kind decides which lead a
reading came off and therefore what a criterion may say about it. Putting the
consequence next to the name keeps the two from drifting apart.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class CoatingType(StrEnum):
    """What the pipe was wrapped in when it went in the ground."""

    BARE = "bare"
    COAL_TAR = "coal_tar"
    ASPHALT = "asphalt"
    TAPE_WRAP = "tape_wrap"
    FUSION_BONDED_EPOXY = "fbe"
    THREE_LAYER_PE = "three_layer_pe"
    LIQUID_EPOXY = "liquid_epoxy"

    @property
    def design_current_density_ma_per_m2(self) -> float:
        """Current the coating is expected to need per square metre of pipe."""
        return _DESIGN_CURRENT_DENSITY[self]

    @property
    def shields_current(self) -> bool:
        """Whether a disbondment under this coating can hide the steel from CP.

        Tape wraps and thick asphalt lift off in sheets and stay watertight
        against the current while letting groundwater underneath. A test point
        can then read fully protected over pipe that is actively corroding, so
        anything on a shielding coating needs an above ground survey rather than
        a potential at a post.
        """
        return self in _SHIELDING_COATINGS


_DESIGN_CURRENT_DENSITY: dict[CoatingType, float] = {
    CoatingType.BARE: 21.5,
    CoatingType.COAL_TAR: 0.16,
    CoatingType.ASPHALT: 0.22,
    CoatingType.TAPE_WRAP: 0.11,
    CoatingType.FUSION_BONDED_EPOXY: 0.03,
    CoatingType.THREE_LAYER_PE: 0.01,
    CoatingType.LIQUID_EPOXY: 0.05,
}

_SHIELDING_COATINGS: frozenset[CoatingType] = frozenset(
    {CoatingType.TAPE_WRAP, CoatingType.ASPHALT}
)


class ProtectionMethod(StrEnum):
    """How a segment is fed current."""

    IMPRESSED_CURRENT = "impressed_current"
    GALVANIC = "galvanic"
    UNPROTECTED = "unprotected"

    @property
    def is_interruptible(self) -> bool:
        """Whether the source can be switched off to take an instant off reading.

        Galvanic anodes cannot be interrupted without lifting a lead, so a
        galvanic segment normally has no instant off potential at all and has to
        be judged on a depolarisation test instead.
        """
        return self is ProtectionMethod.IMPRESSED_CURRENT


class LeadKind(StrEnum):
    """What a lead at a test point is connected to.

    A post carries several wires. Two go to the pipe so the reading is taken
    without any current flowing in the measuring lead, one goes to the casing
    if there is one, one goes to a foreign owner's line at a crossing, and a
    coupon lead goes to a small buried steel disc that stands in for a coating
    holiday. Which wire a number came off decides what may be said about it.
    """

    PIPE = "pipe"
    CASING = "casing"
    FOREIGN = "foreign"
    ANODE = "anode"
    BOND = "bond"
    COUPON = "coupon"
    ISOLATION = "isolation"

    @property
    def carries_structure_potential(self) -> bool:
        """Whether a reading off this lead is a potential on our own pipe."""
        return self in {LeadKind.PIPE, LeadKind.COUPON, LeadKind.ISOLATION}


class SurveyKind(StrEnum):
    """The kinds of field work that produce readings."""

    ANNUAL = "annual"
    CLOSE_INTERVAL = "close_interval"
    DCVG = "dcvg"
    DEPOLARISATION = "depolarisation"
    RECTIFIER_CHECK = "rectifier_check"
    INTERFERENCE = "interference"
    AC_INTERFERENCE = "ac_interference"
    SOIL_RESISTIVITY = "soil_resistivity"

    @property
    def needs_interruption(self) -> bool:
        """Whether the crew has to interrupt the rectifiers to do this work."""
        return self in {SurveyKind.CLOSE_INTERVAL, SurveyKind.DCVG, SurveyKind.ANNUAL}


class ClassLocation(IntEnum):
    """How built up the land over the pipe is, one through four."""

    RURAL = 1
    FRINGE = 2
    SUBURBAN = 3
    URBAN = 4

    @property
    def priority_weight(self) -> float:
        """How much a finding in this class location is escalated."""
        return 1.0 + 0.25 * (self.value - 1)


class SoilCorrosivity(StrEnum):
    """Corrosivity band a resistivity falls into."""

    VERY_CORROSIVE = "very_corrosive"
    CORROSIVE = "corrosive"
    MODERATE = "moderate"
    MILD = "mild"
    BENIGN = "benign"


class Commodity(StrEnum):
    """What the line carries, which decides how hard a leak is taken."""

    NATURAL_GAS = "natural_gas"
    CRUDE_OIL = "crude_oil"
    REFINED_PRODUCTS = "refined_products"
    NATURAL_GAS_LIQUIDS = "ngl"
    CARBON_DIOXIDE = "co2"
    WATER = "water"

    @property
    def is_hazardous_liquid(self) -> bool:
        """Whether a release is a liquid spill rather than a gas escape."""
        return self in {
            Commodity.CRUDE_OIL,
            Commodity.REFINED_PRODUCTS,
            Commodity.NATURAL_GAS_LIQUIDS,
        }
