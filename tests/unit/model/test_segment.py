from __future__ import annotations

import math

import pytest

from dropcell.errors import ValidationError
from dropcell.model.enums import ClassLocation, CoatingType, ProtectionMethod, SoilCorrosivity
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange


def make_segment(**overrides: object) -> Segment:
    kwargs: dict[str, object] = {
        "code": "AL-2-004",
        "line_code": "AL-2",
        "extent": StationRange(Station(0.0), Station(1200.0)),
        "coating": CoatingType.COAL_TAR,
        "protection": ProtectionMethod.IMPRESSED_CURRENT,
        "class_location": ClassLocation.RURAL,
        "outside_diameter_mm": 323.9,
        "wall_thickness_mm": 6.35,
        "installed_year": 1974,
    }
    kwargs.update(overrides)
    return Segment(**kwargs)  # type: ignore[arg-type]


def test_codes_are_normalised_on_the_way_in() -> None:
    segment = make_segment(code=" al 2 004 ", line_code="al-2")
    assert segment.code == "AL-2-004"
    assert segment.line_code == "AL-2"


def test_a_segment_with_no_length_is_refused() -> None:
    with pytest.raises(ValidationError):
        make_segment(extent=StationRange(Station(100.0), Station(100.0)))


def test_a_wall_thicker_than_the_radius_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        make_segment(wall_thickness_mm=200.0)
    assert caught.value.detail["wall_mm"] == pytest.approx(200.0)


@pytest.mark.parametrize("wall", [0.0, -3.0])
def test_a_non_positive_wall_is_refused(wall: float) -> None:
    with pytest.raises(ValidationError):
        make_segment(wall_thickness_mm=wall)


def test_a_non_positive_depth_of_cover_is_refused() -> None:
    with pytest.raises(ValidationError):
        make_segment(depth_of_cover_m=0.0)


def test_a_resistivity_is_optional_but_must_be_positive_when_given() -> None:
    assert make_segment().soil_resistivity_ohm_m is None
    with pytest.raises(ValidationError):
        make_segment(soil_resistivity_ohm_m=-4.0)


def test_the_external_area_is_the_pipe_circumference_times_the_length() -> None:
    segment = make_segment()
    assert segment.external_area_m2 == pytest.approx(math.pi * 0.3239 * 1200.0)


def test_design_current_follows_the_coating() -> None:
    coal_tar = make_segment().design_current_ma
    bare = make_segment(coating=CoatingType.BARE).design_current_ma
    assert bare > coal_tar * 100


def test_corrosivity_comes_back_only_once_the_soil_has_been_measured() -> None:
    assert make_segment().corrosivity is None
    wet = make_segment(soil_resistivity_ohm_m=6.0)
    assert wet.corrosivity is SoilCorrosivity.VERY_CORROSIVE


def test_a_shielding_coating_forces_an_above_ground_survey() -> None:
    assert make_segment(coating=CoatingType.TAPE_WRAP).needs_above_ground_survey
    assert not make_segment(coating=CoatingType.FUSION_BONDED_EPOXY).needs_above_ground_survey


def test_an_unprotected_segment_is_not_protected_by_design() -> None:
    assert make_segment().is_protected_by_design
    assert not make_segment(protection=ProtectionMethod.UNPROTECTED).is_protected_by_design


def test_containment_uses_the_segment_extent() -> None:
    segment = make_segment()
    assert segment.contains(Station(0.0))
    assert segment.contains(Station(1200.0))
    assert not segment.contains(Station(1200.5))


def test_two_segments_of_the_same_line_overlap_when_their_extents_do() -> None:
    first = make_segment(code="A", extent=StationRange(Station(0.0), Station(1200.0)))
    second = make_segment(code="B", extent=StationRange(Station(1100.0), Station(2000.0)))
    third = make_segment(code="C", extent=StationRange(Station(2000.1), Station(3000.0)))
    assert first.overlaps(second)
    assert not second.overlaps(third)


def test_segments_on_different_lines_never_overlap() -> None:
    first = make_segment(code="A")
    other_line = make_segment(code="B", line_code="BR-9")
    assert not first.overlaps(other_line)


def test_notes_stay_out_of_equality() -> None:
    assert make_segment(notes="bored under the A19") == make_segment()
