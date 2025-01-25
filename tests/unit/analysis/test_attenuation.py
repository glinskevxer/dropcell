from __future__ import annotations

import dataclasses
import math

import pytest

from dropcell.analysis.attenuation import (
    COATING_RESISTANCE_OHM_M2,
    attenuation_constant,
    characteristic_resistance,
    for_segment,
    leakage_resistance_ohm_m,
    longitudinal_resistance_ohm_per_m,
    steel_area_m2,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import CoatingType
from dropcell.model.segment import Segment


def test_the_steel_area_is_the_annulus() -> None:
    area = steel_area_m2(323.9, 6.35)
    outer = 0.3239 / 2
    inner = outer - 0.00635
    assert area == pytest.approx(math.pi * (outer**2 - inner**2))


@pytest.mark.parametrize(("od", "wall"), [(0.0, 6.35), (323.9, 0.0), (323.9, 200.0)])
def test_an_impossible_pipe_is_refused(od: float, wall: float) -> None:
    with pytest.raises(ValidationError):
        steel_area_m2(od, wall)


def test_a_thicker_wall_carries_current_better() -> None:
    thin = longitudinal_resistance_ohm_per_m(323.9, 4.0)
    thick = longitudinal_resistance_ohm_per_m(323.9, 12.0)
    assert thick < thin


def test_a_better_coating_leaks_less() -> None:
    poor = leakage_resistance_ohm_m(323.9, 5_000.0)
    good = leakage_resistance_ohm_m(323.9, 300_000.0)
    assert good > poor


def test_a_coating_with_no_resistance_is_refused() -> None:
    with pytest.raises(ValidationError):
        leakage_resistance_ohm_m(323.9, 0.0)


def test_the_attenuation_constant_is_the_root_of_the_ratio() -> None:
    assert attenuation_constant(4.0, 100.0) == pytest.approx(0.2)


def test_the_characteristic_resistance_is_the_root_of_the_product() -> None:
    assert characteristic_resistance(4.0, 100.0) == pytest.approx(20.0)


@pytest.mark.parametrize(("longitudinal", "leakage"), [(0.0, 100.0), (4.0, 0.0)])
def test_a_resistance_of_nothing_is_refused(longitudinal: float, leakage: float) -> None:
    with pytest.raises(ValidationError):
        attenuation_constant(longitudinal, leakage)
    with pytest.raises(ValidationError):
        characteristic_resistance(longitudinal, leakage)


def test_every_coating_carries_a_resistance() -> None:
    for coating in CoatingType:
        assert COATING_RESISTANCE_OHM_M2[str(coating)] > 0


def test_a_well_coated_segment_attenuates_more_slowly(segment: Segment) -> None:
    coated = for_segment(dataclasses.replace(segment, coating=CoatingType.THREE_LAYER_PE))
    bare = for_segment(dataclasses.replace(segment, coating=CoatingType.BARE))
    assert coated.alpha_per_m < bare.alpha_per_m


def test_the_half_length_falls_out_of_the_constant(segment: Segment) -> None:
    model = for_segment(segment)
    assert model.half_length_m == pytest.approx(math.log(2.0) / model.alpha_per_m)
    assert model.shift_at(300.0, model.half_length_m) == pytest.approx(150.0)


def test_the_shift_at_the_drain_point_is_the_whole_shift(segment: Segment) -> None:
    assert for_segment(segment).shift_at(300.0, 0.0) == pytest.approx(300.0)


def test_the_shift_falls_off_with_distance(segment: Segment) -> None:
    model = for_segment(segment)
    near = model.shift_at(300.0, 100.0)
    far = model.shift_at(300.0, 1000.0)
    assert far < near < 300.0


def test_a_negative_distance_is_refused(segment: Segment) -> None:
    with pytest.raises(ValidationError):
        for_segment(segment).shift_at(300.0, -1.0)


def test_the_reach_is_where_the_shift_falls_to_what_is_needed(
    segment: Segment,
) -> None:
    model = for_segment(segment)
    reach = model.reach_m(300.0, 100.0)
    assert model.shift_at(300.0, reach) == pytest.approx(100.0)


def test_a_bare_line_reaches_far_less_than_a_coated_one(segment: Segment) -> None:
    coated = for_segment(dataclasses.replace(segment, coating=CoatingType.FUSION_BONDED_EPOXY))
    bare = for_segment(dataclasses.replace(segment, coating=CoatingType.BARE))
    assert coated.reach_m(300.0, 100.0) > bare.reach_m(300.0, 100.0) * 100


def test_a_required_shift_the_drain_point_cannot_meet_reaches_nothing(
    segment: Segment,
) -> None:
    model = for_segment(segment)
    assert model.reach_m(100.0, 100.0) == pytest.approx(0.0)
    assert model.reach_m(100.0, 300.0) == pytest.approx(0.0)


def test_shifts_of_nothing_are_refused(segment: Segment) -> None:
    model = for_segment(segment)
    with pytest.raises(ValidationError):
        model.reach_m(0.0, 100.0)
    with pytest.raises(ValidationError):
        model.reach_m(300.0, 0.0)


def test_the_spacing_is_twice_the_reach(segment: Segment) -> None:
    model = for_segment(segment)
    assert model.spacing_m(300.0, 100.0) == pytest.approx(2 * model.reach_m(300.0, 100.0))


def test_a_measured_coating_resistance_beats_the_table(segment: Segment) -> None:
    from_table = for_segment(segment)
    measured = for_segment(segment, coating_resistance_ohm_m2=200.0)
    assert measured.alpha_per_m > from_table.alpha_per_m


def test_the_model_carries_the_segment_it_was_built_from(segment: Segment) -> None:
    assert for_segment(segment).segment_code == "AL-2-004"
