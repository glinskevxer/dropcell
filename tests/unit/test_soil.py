from __future__ import annotations

import math

import pytest

from dropcell.errors import ValidationError
from dropcell.model.enums import SoilCorrosivity
from dropcell.soil import (
    SoilLayer,
    barnes_layers,
    classify_corrosivity,
    resistivity_at_depth,
    wenner_resistivity_ohm_m,
)


def test_wenner_is_two_pi_a_r() -> None:
    assert wenner_resistivity_ohm_m(1.5, 4.0) == pytest.approx(2 * math.pi * 1.5 * 4.0)


@pytest.mark.parametrize(("spacing", "resistance"), [(0.0, 4.0), (-1.0, 4.0), (1.5, 0.0)])
def test_wenner_refuses_a_reading_that_cannot_be_real(
    spacing: float, resistance: float
) -> None:
    with pytest.raises(ValidationError):
        wenner_resistivity_ohm_m(spacing, resistance)


@pytest.mark.parametrize(
    ("resistivity", "band"),
    [
        (5.0, SoilCorrosivity.VERY_CORROSIVE),
        (9.99, SoilCorrosivity.VERY_CORROSIVE),
        (10.0, SoilCorrosivity.CORROSIVE),
        (19.9, SoilCorrosivity.CORROSIVE),
        (20.0, SoilCorrosivity.MODERATE),
        (49.0, SoilCorrosivity.MODERATE),
        (50.0, SoilCorrosivity.MILD),
        (99.0, SoilCorrosivity.MILD),
        (100.0, SoilCorrosivity.BENIGN),
        (4000.0, SoilCorrosivity.BENIGN),
    ],
)
def test_the_corrosivity_bands_are_closed_at_the_bottom(
    resistivity: float, band: SoilCorrosivity
) -> None:
    assert classify_corrosivity(resistivity) is band


def test_a_non_positive_resistivity_has_no_band() -> None:
    with pytest.raises(ValidationError):
        classify_corrosivity(0.0)


def test_a_layer_knows_its_thickness_and_its_band() -> None:
    layer = SoilLayer(top_m=0.0, bottom_m=1.5, resistivity_ohm_m=8.0)
    assert layer.thickness_m == pytest.approx(1.5)
    assert layer.corrosivity is SoilCorrosivity.VERY_CORROSIVE


def test_a_layer_holds_its_top_and_excludes_its_bottom() -> None:
    layer = SoilLayer(top_m=1.5, bottom_m=3.0, resistivity_ohm_m=40.0)
    assert layer.contains_depth(1.5)
    assert layer.contains_depth(2.9)
    assert not layer.contains_depth(3.0)
    assert not layer.contains_depth(1.4)


def test_uniform_ground_gives_layers_of_the_same_resistivity() -> None:
    rho = 2 * math.pi * 1.0 * 10.0
    layers = barnes_layers([(1.0, 10.0), (2.0, 5.0), (3.0, 10.0 / 3.0)])
    assert [layer.resistivity_ohm_m for layer in layers] == pytest.approx([rho, rho, rho])


def test_layers_stack_from_the_surface_down_by_the_spacing_step() -> None:
    layers = barnes_layers([(0.5, 20.0), (1.0, 10.0)])
    assert (layers[0].top_m, layers[0].bottom_m) == pytest.approx((0.0, 0.5))
    assert (layers[1].top_m, layers[1].bottom_m) == pytest.approx((0.5, 1.0))


def test_a_conductive_layer_underneath_shows_up_as_low_resistivity() -> None:
    layers = barnes_layers([(1.0, 20.0), (2.0, 4.0)])
    assert layers[1].resistivity_ohm_m < layers[0].resistivity_ohm_m


def test_barnes_sorts_the_readings_before_it_differences_them() -> None:
    forward = barnes_layers([(1.0, 20.0), (2.0, 8.0)])
    shuffled = barnes_layers([(2.0, 8.0), (1.0, 20.0)])
    assert forward == shuffled


def test_one_spacing_is_not_a_sounding() -> None:
    with pytest.raises(ValidationError):
        barnes_layers([(1.0, 10.0)])


def test_uneven_spacings_are_refused_rather_than_averaged() -> None:
    with pytest.raises(ValidationError) as caught:
        barnes_layers([(1.0, 20.0), (2.5, 8.0)])
    assert caught.value.detail["expected_m"] == pytest.approx(2.0)


def test_resistance_rising_with_depth_cannot_be_resolved() -> None:
    with pytest.raises(ValidationError) as caught:
        barnes_layers([(1.0, 10.0), (2.0, 12.0)])
    assert caught.value.detail["layer"] == 2


def test_a_pipe_gets_the_resistivity_of_the_layer_it_lies_in() -> None:
    layers = barnes_layers([(1.0, 20.0), (2.0, 4.0)])
    assert resistivity_at_depth(layers, 0.5) == pytest.approx(layers[0].resistivity_ohm_m)
    assert resistivity_at_depth(layers, 1.5) == pytest.approx(layers[1].resistivity_ohm_m)


def test_a_depth_below_the_sounding_falls_back_to_the_deepest_layer() -> None:
    layers = barnes_layers([(1.0, 20.0), (2.0, 4.0)])
    assert resistivity_at_depth(layers, 9.0) == pytest.approx(layers[-1].resistivity_ohm_m)


def test_a_negative_depth_is_refused() -> None:
    with pytest.raises(ValidationError):
        resistivity_at_depth(barnes_layers([(1.0, 20.0), (2.0, 4.0)]), -0.2)
