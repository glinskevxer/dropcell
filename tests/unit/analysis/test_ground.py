from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.ground import (
    WIDE_MARGIN,
    assess_ground,
    assess_line,
    understated,
)
from dropcell.model.enums import SoilCorrosivity
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange
from dropcell.store.soundings import Sounding

LAYERED = ((1.0, 31.831), (2.0, 2.2208), (3.0, 1.8018))
"""A sounding whose top metre is benign and whose second metre is corrosive.

Worked back from the Barnes arithmetic so the layers come out at roughly 200,
15 and 60 ohm m. The point of it is that a pipe at 1.2 m is lying in the middle
layer, and nothing measured at the surface says so.
"""

FLAT = ((1.0, 4.7746), (2.0, 2.3873), (3.0, 1.5915))
"""Thirty ohm m all the way down, so depth cannot change the answer."""


def sounding_at(metres: float, readings: tuple[tuple[float, float], ...] = LAYERED) -> Sounding:
    """A sounding on the example line at a station."""
    return Sounding(
        line_code="AL-2",
        station=Station(metres),
        measured_on=dt.date(2025, 2, 20),
        readings=readings,
        sounding_id=1,
    )


def test_the_layered_sounding_is_benign_on_top_and_corrosive_at_pipe_depth() -> None:
    ground = sounding_at(600.0)
    assert ground.layers[0].corrosivity is SoilCorrosivity.BENIGN
    assert ground.corrosivity_at(1.2) == SoilCorrosivity.CORROSIVE


def test_a_segment_is_read_at_its_own_depth_of_cover(segment: Segment) -> None:
    shallow = dataclasses.replace(segment, depth_of_cover_m=0.5)
    deep = dataclasses.replace(segment, depth_of_cover_m=1.5)
    ground = sounding_at(600.0)

    assert assess_ground(shallow, ground).measured_band is SoilCorrosivity.BENIGN
    assert assess_ground(deep, ground).measured_band is SoilCorrosivity.CORROSIVE


def test_a_benign_filed_figure_over_a_corrosive_layer_is_understated(segment: Segment) -> None:
    buried = dataclasses.replace(segment, depth_of_cover_m=1.2, soil_resistivity_ohm_m=200.0)
    result = assess_ground(buried, sounding_at(600.0))

    assert result.filed_band is SoilCorrosivity.BENIGN
    assert result.measured_band is SoilCorrosivity.CORROSIVE
    assert result.understates
    assert not result.overstates
    assert not result.bands_agree
    assert result.verdict == "understated"


def test_a_harsh_filed_figure_over_mild_ground_is_overstated(segment: Segment) -> None:
    buried = dataclasses.replace(segment, depth_of_cover_m=2.5, soil_resistivity_ohm_m=8.0)
    result = assess_ground(buried, sounding_at(600.0))

    assert result.measured_band is SoilCorrosivity.MILD
    assert result.overstates
    assert not result.understates
    assert result.verdict == "overstated"


def test_matching_figures_agree(segment: Segment) -> None:
    buried = dataclasses.replace(segment, depth_of_cover_m=1.2, soil_resistivity_ohm_m=30.0)
    result = assess_ground(buried, sounding_at(600.0, FLAT))

    assert result.bands_agree
    assert not result.is_far_off
    assert result.verdict == "agrees"


def test_two_numbers_can_share_a_band_and_still_be_far_apart(segment: Segment) -> None:
    """Benign runs from a hundred upwards, so two benign numbers can be miles apart."""
    buried = dataclasses.replace(segment, depth_of_cover_m=0.5, soil_resistivity_ohm_m=1000.0)
    result = assess_ground(buried, sounding_at(600.0))

    assert result.measured_band is SoilCorrosivity.BENIGN
    assert result.filed_band is SoilCorrosivity.BENIGN
    assert result.bands_agree
    assert result.ratio is not None
    assert result.ratio == pytest.approx(5.0, rel=1e-3)
    assert result.ratio > WIDE_MARGIN
    assert result.is_far_off
    assert result.verdict == "same band, wide"


def test_a_bounded_band_is_too_narrow_for_the_margin_to_fire(segment: Segment) -> None:
    """Mild runs fifty to a hundred, so nothing inside it can be a factor of two out."""
    buried = dataclasses.replace(segment, depth_of_cover_m=2.5, soil_resistivity_ohm_m=51.0)
    result = assess_ground(buried, sounding_at(600.0))

    assert result.measured_band is SoilCorrosivity.MILD
    assert result.bands_agree
    assert not result.is_far_off
    assert result.verdict == "agrees"


def test_a_segment_with_nothing_filed_is_not_a_disagreement(segment: Segment) -> None:
    buried = dataclasses.replace(segment, depth_of_cover_m=1.2, soil_resistivity_ohm_m=None)
    result = assess_ground(buried, sounding_at(600.0))

    assert not result.has_filed_figure
    assert result.filed_band is None
    assert result.ratio is None
    assert result.bands_agree
    assert not result.understates
    assert not result.overstates
    assert result.verdict == "not filed"


def test_the_explanation_says_what_was_compared(segment: Segment) -> None:
    buried = dataclasses.replace(segment, depth_of_cover_m=1.2, soil_resistivity_ohm_m=200.0)
    line = assess_ground(buried, sounding_at(600.0)).explain()

    assert "1.2 m" in line
    assert "corrosive" in line
    assert "understated" in line


def test_the_explanation_says_so_when_nothing_is_filed(segment: Segment) -> None:
    buried = dataclasses.replace(segment, soil_resistivity_ohm_m=None)
    assert "nothing filed against it" in assess_ground(buried, sounding_at(600.0)).explain()


def test_each_segment_takes_the_nearest_sounding(segment: Segment) -> None:
    near = dataclasses.replace(segment, code="AL-2-001")
    far = dataclasses.replace(
        segment,
        code="AL-2-009",
        extent=StationRange(Station(9000.0), Station(10_000.0)),
    )
    flat = sounding_at(9500.0, FLAT)
    layered = sounding_at(600.0)

    results = {item.segment_code: item for item in assess_line([near, far], [layered, flat])}

    assert results["AL-2-001"].measured_ohm_m == pytest.approx(15.0, rel=1e-3)
    assert results["AL-2-009"].measured_ohm_m == pytest.approx(30.0, rel=1e-3)


def test_the_distance_is_measured_from_the_middle_of_the_segment(segment: Segment) -> None:
    result = assess_line([segment], [sounding_at(1000.0)])[0]
    assert result.distance_m == pytest.approx(400.0)


def test_a_line_with_no_soundings_gives_nothing_rather_than_false_agreement(
    segment: Segment,
) -> None:
    assert assess_line([segment], []) == []


def test_understated_comes_back_worst_first(segment: Segment) -> None:
    badly = dataclasses.replace(
        segment, code="AL-2-001", depth_of_cover_m=1.2, soil_resistivity_ohm_m=200.0
    )
    slightly = dataclasses.replace(
        segment,
        code="AL-2-002",
        extent=StationRange(Station(1200.0), Station(2400.0)),
        depth_of_cover_m=1.2,
        soil_resistivity_ohm_m=22.0,
    )
    fine = dataclasses.replace(
        segment,
        code="AL-2-003",
        extent=StationRange(Station(2400.0), Station(3600.0)),
        depth_of_cover_m=1.2,
        soil_resistivity_ohm_m=15.0,
    )
    results = assess_line([badly, slightly, fine], [sounding_at(1800.0)])

    assert [item.segment_code for item in understated(results)] == ["AL-2-001", "AL-2-002"]


def test_the_band_ordering_covers_every_band() -> None:
    """A band missing from the ordering would raise rather than sort wrongly."""
    from dropcell.analysis.ground import BAND_ORDER

    assert set(BAND_ORDER) == set(SoilCorrosivity)
