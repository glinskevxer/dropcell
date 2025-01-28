from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from dropcell.analysis.demand import (
    MAX_BREAKDOWN,
    breakdown_factor,
    line_demand,
    segment_demand,
)
from dropcell.errors import ValidationError
from dropcell.model.enums import CoatingType
from dropcell.model.rectifier import Rectifier
from dropcell.model.segment import Segment
from dropcell.stationing import Station


def unit(amps: float, tag: str = "RU-1") -> Rectifier:
    return Rectifier(
        tag=tag,
        line_code="AL-2",
        station=Station(100.0),
        groundbed_code="GB-1",
        rated_voltage_v=24.0,
        rated_current_a=amps,
        coarse_taps=5,
        fine_taps=4,
        installed_on=dt.date(2004, 9, 1),
    )


def test_a_new_coating_draws_what_the_table_says() -> None:
    assert breakdown_factor(0) == pytest.approx(1.0)


def test_an_older_coating_draws_more() -> None:
    assert breakdown_factor(10) == pytest.approx(1.2)
    assert breakdown_factor(50) == pytest.approx(2.0)


def test_the_breakdown_is_capped() -> None:
    assert breakdown_factor(10_000) == pytest.approx(MAX_BREAKDOWN)


def test_a_negative_age_is_refused() -> None:
    with pytest.raises(ValidationError):
        breakdown_factor(-1)


def test_a_coating_that_improves_with_age_is_refused() -> None:
    with pytest.raises(ValidationError):
        breakdown_factor(10, per_year=-0.01)


def test_a_segment_asks_for_its_area_times_its_density(segment: Segment) -> None:
    demand = segment_demand(segment, as_of_year=1974)
    assert demand.area_m2 == pytest.approx(segment.external_area_m2)
    assert demand.new_current_ma == pytest.approx(segment.design_current_ma)
    assert demand.breakdown == pytest.approx(1.0)


def test_an_old_segment_asks_for_more_than_a_new_one(segment: Segment) -> None:
    new = segment_demand(segment, as_of_year=1974)
    old = segment_demand(segment, as_of_year=2025)
    assert old.current_a > new.current_a


def test_a_segment_installed_after_the_year_asked_about_is_treated_as_new(
    segment: Segment,
) -> None:
    assert segment_demand(segment, as_of_year=1900).breakdown == pytest.approx(1.0)


def test_bare_pipe_asks_for_far_more_than_epoxy(segment: Segment) -> None:
    bare = segment_demand(
        dataclasses.replace(segment, coating=CoatingType.BARE), as_of_year=2025
    )
    epoxy = segment_demand(
        dataclasses.replace(segment, coating=CoatingType.FUSION_BONDED_EPOXY),
        as_of_year=2025,
    )
    assert bare.current_a > epoxy.current_a * 100


def test_a_line_adds_its_segments_up(segment: Segment) -> None:
    second = dataclasses.replace(segment, code="AL-2-005")
    demand = line_demand("AL-2", [segment, second], [unit(20.0)], as_of_year=2025)
    assert demand.bare_demand_a == pytest.approx(
        2 * segment_demand(segment, as_of_year=2025).current_a
    )


def test_the_design_demand_carries_the_allowance(segment: Segment) -> None:
    demand = line_demand("AL-2", [segment], [unit(20.0)], as_of_year=2025)
    assert demand.design_demand_a == pytest.approx(demand.bare_demand_a * 1.25)


def test_the_design_factor_can_be_moved(segment: Segment) -> None:
    demand = line_demand("AL-2", [segment], [unit(20.0)], as_of_year=2025, design_factor=2.0)
    assert demand.design_demand_a == pytest.approx(demand.bare_demand_a * 2.0)


def test_a_design_factor_below_one_is_refused(segment: Segment) -> None:
    with pytest.raises(ValidationError):
        line_demand("AL-2", [segment], [], as_of_year=2025, design_factor=0.8)


def test_a_line_with_plenty_of_capacity_has_headroom(segment: Segment) -> None:
    demand = line_demand("AL-2", [segment], [unit(20.0)], as_of_year=2025)
    assert demand.headroom_a > 0
    assert not demand.is_short
    assert not demand.cannot_protect


def test_a_line_short_of_the_design_demand_is_a_planning_problem(
    segment: Segment,
) -> None:
    bare = dataclasses.replace(segment, coating=CoatingType.BARE)
    without_margin = line_demand("AL-2", [bare], [], as_of_year=2025).bare_demand_a
    demand = line_demand("AL-2", [bare], [unit(without_margin * 1.1)], as_of_year=2025)
    assert demand.is_short
    assert not demand.cannot_protect


def test_a_line_short_of_the_bare_demand_cannot_be_protected(
    segment: Segment,
) -> None:
    bare = dataclasses.replace(segment, coating=CoatingType.BARE)
    demand = line_demand("AL-2", [bare], [unit(1.0)], as_of_year=2025)
    assert demand.cannot_protect
    assert demand.is_short


def test_a_line_with_no_rectifiers_cannot_protect_anything(segment: Segment) -> None:
    demand = line_demand("AL-2", [segment], [], as_of_year=2025)
    assert demand.installed_a == pytest.approx(0.0)
    assert demand.cannot_protect
    assert demand.utilisation == float("inf")


def test_a_line_with_no_segments_asks_for_nothing() -> None:
    demand = line_demand("AL-2", [], [], as_of_year=2025)
    assert demand.bare_demand_a == pytest.approx(0.0)
    assert demand.utilisation == pytest.approx(0.0)
    assert not demand.cannot_protect


def test_several_rectifiers_add_their_ratings(segment: Segment) -> None:
    demand = line_demand("AL-2", [segment], [unit(20.0), unit(30.0, "RU-2")], as_of_year=2025)
    assert demand.installed_a == pytest.approx(50.0)


def test_utilisation_is_the_demand_over_the_capacity(segment: Segment) -> None:
    demand = line_demand("AL-2", [segment], [unit(20.0)], as_of_year=2025)
    assert demand.utilisation == pytest.approx(demand.bare_demand_a / 20.0)


def test_segments_come_back_ordered_by_what_they_ask_for(segment: Segment) -> None:
    small = dataclasses.replace(segment, code="AL-2-004")
    large = dataclasses.replace(segment, code="AL-2-005", coating=CoatingType.BARE)
    demand = line_demand("AL-2", [small, large], [unit(20.0)], as_of_year=2025)
    assert [item.segment_code for item in demand.worst_first()] == [
        "AL-2-005",
        "AL-2-004",
    ]
