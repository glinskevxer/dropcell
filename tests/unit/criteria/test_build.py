from __future__ import annotations

import dataclasses

import pytest

from dropcell.config import Settings
from dropcell.criteria.base import Evidence
from dropcell.criteria.build import anaerobic_threshold, build_set, limits_for, select_for
from dropcell.criteria.potential import PolarisedPotentialCriterion
from dropcell.model.enums import CoatingType, ProtectionMethod
from dropcell.model.segment import Segment


def evidence(segment: Segment, **overrides: object) -> Evidence:
    return Evidence(segment=segment, **overrides)  # type: ignore[arg-type]


def test_the_default_settings_reproduce_the_shipped_threshold() -> None:
    built = build_set(Settings(), name="impressed_current")
    polarised = [
        item for item in built.criteria if isinstance(item, PolarisedPotentialCriterion)
    ]
    assert polarised[0].threshold_mv == pytest.approx(-850.0)


def test_a_tighter_criterion_moves_into_the_set(segment: Segment) -> None:
    built = build_set(Settings(protection_mv=-950.0), name="impressed_current")
    result = built.evaluate(evidence(segment, off_mv=-905.0))
    assert result.by_key("polarised_potential") is not None
    assert not result.protected


def test_the_anaerobic_threshold_moves_with_the_ordinary_one() -> None:
    assert anaerobic_threshold(Settings()) == pytest.approx(-950.0)
    assert anaerobic_threshold(Settings(protection_mv=-950.0)) == pytest.approx(-1050.0)


def test_the_anaerobic_set_uses_the_moved_threshold(segment: Segment) -> None:
    built = build_set(Settings(protection_mv=-950.0), name="anaerobic", anaerobic=True)
    polarised = [
        item for item in built.criteria if isinstance(item, PolarisedPotentialCriterion)
    ]
    assert polarised[0].threshold_mv == pytest.approx(-1050.0)


def test_a_moved_decay_criterion_lands_in_the_set(segment: Segment) -> None:
    built = build_set(Settings(decay_mv=150.0), name="impressed_current")
    result = built.evaluate(evidence(segment, off_mv=-780.0, depolarised_mv=-660.0))
    assert result.by_key("polarisation_decay") is not None
    assert not result.protected


def test_the_galvanic_set_admits_the_on_potential() -> None:
    built = build_set(Settings(), name="galvanic", galvanic=True)
    assert "on_potential" in built.keys


def test_the_ordinary_set_does_not() -> None:
    assert "on_potential" not in build_set(Settings(), name="impressed_current").keys


def test_the_ac_limits_only_appear_when_asked_for() -> None:
    plain = {item.key for item in limits_for(Settings(), with_ac=False)}  # type: ignore[attr-defined]
    withac = {item.key for item in limits_for(Settings(), with_ac=True)}  # type: ignore[attr-defined]
    assert "ac_current_density" not in plain
    assert plain < withac


def test_the_ac_bands_come_from_the_settings(segment: Segment) -> None:
    built = build_set(
        Settings(ac_low_risk_a_per_m2=5.0, ac_high_risk_a_per_m2=10.0),
        name="ac_interference",
        ac_interference=True,
    )
    result = built.evaluate(evidence(segment, ac_current_density_a_per_m2=12.0))
    exceeded = [item.criterion for item in result.exceeded]
    assert "ac_current_density" in exceeded


def test_the_same_density_is_fine_at_the_shipped_bands(segment: Segment) -> None:
    built = build_set(Settings(), name="ac_interference", ac_interference=True)
    result = built.evaluate(evidence(segment, ac_current_density_a_per_m2=12.0))
    assert result.exceeded == ()


def test_the_selection_keeps_the_shipped_reasons(segment: Segment) -> None:
    chosen = select_for(segment, Settings())
    assert chosen.name == "impressed_current"
    assert "rectifier" in chosen.reasons[0]


def test_the_selection_rebuilds_the_set_at_the_local_figures(
    segment: Segment,
) -> None:
    chosen = select_for(segment, Settings(protection_mv=-950.0))
    result = chosen.criterion_set.evaluate(evidence(segment, off_mv=-905.0))
    assert not result.protected


def test_a_galvanic_segment_still_gets_the_galvanic_set(segment: Segment) -> None:
    anodes = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    chosen = select_for(anodes, Settings())
    assert chosen.name == "galvanic"
    assert "on_potential" in chosen.criterion_set.keys


def test_an_unprotected_segment_gets_the_shipped_empty_set(segment: Segment) -> None:
    bare = dataclasses.replace(segment, protection=ProtectionMethod.UNPROTECTED)
    chosen = select_for(bare, Settings())
    assert chosen.name == "unprotected"
    assert chosen.criterion_set.keys == ()


def test_a_shielding_coating_still_says_posts_are_not_enough(
    segment: Segment,
) -> None:
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    assert not select_for(taped, Settings()).posts_are_enough


def test_ac_interference_still_beats_anaerobic_soil(segment: Segment) -> None:
    chosen = select_for(segment, Settings(), anaerobic=True, ac_interference=True)
    assert chosen.name == "ac_interference"
    assert "ac_current_density" in chosen.criterion_set.keys


def test_the_over_protection_limit_is_still_in_every_built_set(
    segment: Segment,
) -> None:
    built = [
        build_set(Settings(), name="impressed_current"),
        build_set(Settings(), name="galvanic", galvanic=True),
        build_set(Settings(), name="anaerobic", anaerobic=True),
        build_set(Settings(), name="ac_interference", ac_interference=True),
    ]
    for item in built:
        assert "over_protection" in item.keys


def test_a_built_set_carries_a_description(segment: Segment) -> None:
    assert build_set(Settings(), name="x").description == "built from the settings in force"
