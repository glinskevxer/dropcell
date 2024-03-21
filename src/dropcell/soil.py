"""Soil resistivity, and what it says about how hard the ground is on steel.

Resistivity is measured with a four pin Wenner set: four rods in a line at equal
spacing, current through the outer pair, voltage across the inner pair. The
resistance that falls out is turned into a bulk resistivity by

    rho = 2 * pi * a * R

where ``a`` is the pin spacing in metres. The result is an average down to
roughly one pin spacing, so a set of readings taken at increasing spacings
describes deeper and deeper averages rather than separate layers.

Pulling the layers back out of those averages is the Barnes method. Conductance
adds in parallel, so the conductance of the layer between two spacings is the
difference of the two measured conductances, and the resistivity of that layer
follows from its own thickness. It matters because a pipe at 1.5 m does not
care about the average down to 5 m, it cares about the metre it is lying in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.model.enums import SoilCorrosivity

CORROSIVITY_BANDS: list[tuple[float, SoilCorrosivity]] = [
    (10.0, SoilCorrosivity.VERY_CORROSIVE),
    (20.0, SoilCorrosivity.CORROSIVE),
    (50.0, SoilCorrosivity.MODERATE),
    (100.0, SoilCorrosivity.MILD),
]


def wenner_resistivity_ohm_m(spacing_m: float, resistance_ohm: float) -> float:
    """Bulk resistivity from one four pin reading."""
    if spacing_m <= 0:
        raise ValidationError("pin spacing must be positive", spacing_m=spacing_m)
    if resistance_ohm <= 0:
        raise ValidationError("resistance must be positive", resistance_ohm=resistance_ohm)
    return 2.0 * math.pi * spacing_m * resistance_ohm


def classify_corrosivity(resistivity_ohm_m: float) -> SoilCorrosivity:
    """Put a resistivity in the band field crews and engineers argue in."""
    if resistivity_ohm_m <= 0:
        raise ValidationError("resistivity must be positive", value=resistivity_ohm_m)
    for limit, band in CORROSIVITY_BANDS:
        if resistivity_ohm_m < limit:
            return band
    return SoilCorrosivity.BENIGN


@dataclass(frozen=True)
class SoilLayer:
    """One slice of ground between two depths, with its own resistivity."""

    top_m: float
    bottom_m: float
    resistivity_ohm_m: float

    @property
    def thickness_m(self) -> float:
        """How thick the slice is."""
        return self.bottom_m - self.top_m

    @property
    def corrosivity(self) -> SoilCorrosivity:
        """The band this layer falls in."""
        return classify_corrosivity(self.resistivity_ohm_m)

    def contains_depth(self, depth_m: float) -> bool:
        """Whether a buried depth falls in this layer."""
        return self.top_m <= depth_m < self.bottom_m


def barnes_layers(readings: list[tuple[float, float]]) -> list[SoilLayer]:
    """Split a Wenner sounding into layers by the Barnes method.

    ``readings`` is a list of ``(spacing_m, resistance_ohm)`` pairs taken at
    equally increasing spacings. The spacing increment sets the layer thickness,
    so an uneven set is refused rather than quietly averaged.
    """
    if len(readings) < 2:
        raise ValidationError("Barnes needs at least two spacings", count=len(readings))
    ordered = sorted(readings)
    step = ordered[0][0]
    for index, (spacing, resistance) in enumerate(ordered, start=1):
        if resistance <= 0:
            raise ValidationError("resistance must be positive", resistance_ohm=resistance)
        if not math.isclose(spacing, step * index, rel_tol=1e-6):
            raise ValidationError(
                "Barnes needs equally spaced pin settings",
                spacing_m=spacing,
                expected_m=step * index,
            )
    layers: list[SoilLayer] = []
    previous_conductance = 0.0
    for index, (_, resistance) in enumerate(ordered):
        conductance = 1.0 / resistance
        layer_conductance = conductance - previous_conductance
        if layer_conductance <= 0:
            raise ValidationError(
                "conductance fell with depth, which the method cannot resolve",
                layer=index + 1,
            )
        layers.append(
            SoilLayer(
                top_m=step * index,
                bottom_m=step * (index + 1),
                resistivity_ohm_m=2.0 * math.pi * step / layer_conductance,
            )
        )
        previous_conductance = conductance
    return layers


def resistivity_at_depth(layers: list[SoilLayer], depth_m: float) -> float:
    """Resistivity of the layer a pipe at that depth is lying in."""
    if depth_m < 0:
        raise ValidationError("depth cannot be negative", depth_m=depth_m)
    for layer in layers:
        if layer.contains_depth(depth_m):
            return layer.resistivity_ohm_m
    if layers and depth_m >= layers[-1].bottom_m:
        return layers[-1].resistivity_ohm_m
    raise ValidationError("no layer covers that depth", depth_m=depth_m)
