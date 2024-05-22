from __future__ import annotations

import dataclasses

import pytest

from dropcell.criteria.potential import ANAEROBIC_PROTECTION_MV, PolarisedPotentialCriterion
from dropcell.criteria.registry import (
    AC_INTERFERENCE,
    ANAEROBIC,
    GALVANIC,
    IMPRESSED_CURRENT,
    SETS,
    UNPROTECTED,
    get_set,
    select_set,
)
from dropcell.errors import PolicyError
from dropcell.model.enums import CoatingType, ProtectionMethod
from dropcell.model.segment import Segment


def test_every_set_is_registered_under_its_own_name() -> None:
    for name, criterion_set in SETS.items():
        assert criterion_set.name == name


def test_a_set_can_be_looked_up_by_name() -> None:
    assert get_set("impressed_current") is IMPRESSED_CURRENT


def test_an_unknown_set_name_lists_the_ones_that_exist() -> None:
    with pytest.raises(PolicyError) as caught:
        get_set("wishful")
    assert "impressed_current" in caught.value.detail["known"]


def test_the_impressed_current_set_does_not_admit_the_on_potential() -> None:
    assert "on_potential" not in IMPRESSED_CURRENT.keys


def test_the_galvanic_set_does() -> None:
    assert "on_potential" in GALVANIC.keys


def test_the_anaerobic_set_carries_the_tighter_threshold() -> None:
    polarised = [
        item for item in ANAEROBIC.criteria if isinstance(item, PolarisedPotentialCriterion)
    ]
    assert polarised[0].threshold_mv == pytest.approx(ANAEROBIC_PROTECTION_MV)


def test_the_ac_set_adds_the_ac_limits_to_the_ordinary_ones() -> None:
    ordinary_limits = {item.key for item in IMPRESSED_CURRENT.limits}
    ac_limits = {item.key for item in AC_INTERFERENCE.limits}
    assert ordinary_limits < ac_limits
    assert "ac_current_density" in ac_limits
    assert "touch_voltage" in ac_limits


def test_an_unprotected_segment_gets_a_set_with_nothing_in_it(segment: Segment) -> None:
    bare = dataclasses.replace(segment, protection=ProtectionMethod.UNPROTECTED)
    selection = select_set(bare)
    assert selection.criterion_set is UNPROTECTED
    assert selection.criterion_set.keys == ()
    assert not selection.posts_are_enough


def test_a_rectifier_fed_segment_gets_the_ordinary_set(segment: Segment) -> None:
    selection = select_set(segment)
    assert selection.name == "impressed_current"
    assert selection.posts_are_enough
    assert "rectifier" in selection.reasons[0]


def test_a_galvanic_segment_gets_the_galvanic_set(segment: Segment) -> None:
    anodes = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    assert select_set(anodes).criterion_set is GALVANIC


def test_anaerobic_soil_takes_the_tightened_set(segment: Segment) -> None:
    selection = select_set(segment, anaerobic=True)
    assert selection.criterion_set is ANAEROBIC
    assert "sulfate" in selection.reasons[0]


def test_ac_interference_beats_anaerobic_soil(segment: Segment) -> None:
    selection = select_set(segment, anaerobic=True, ac_interference=True)
    assert selection.criterion_set is AC_INTERFERENCE
    assert any("anaerobic soil noted" in reason for reason in selection.reasons)


def test_ac_interference_beats_the_galvanic_set_too(segment: Segment) -> None:
    anodes = dataclasses.replace(segment, protection=ProtectionMethod.GALVANIC)
    assert select_set(anodes, ac_interference=True).criterion_set is AC_INTERFERENCE


def test_an_unprotected_segment_ignores_both_flags(segment: Segment) -> None:
    bare = dataclasses.replace(segment, protection=ProtectionMethod.UNPROTECTED)
    selection = select_set(bare, anaerobic=True, ac_interference=True)
    assert selection.criterion_set is UNPROTECTED
    assert len(selection.reasons) == 1


def test_a_shielding_coating_says_posts_are_not_enough(segment: Segment) -> None:
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    selection = select_set(taped)
    assert not selection.posts_are_enough
    assert any("shield" in reason for reason in selection.reasons)


def test_the_coating_does_not_change_which_criteria_apply(segment: Segment) -> None:
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    assert select_set(taped).criterion_set is select_set(segment).criterion_set
