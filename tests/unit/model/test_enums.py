from __future__ import annotations

import pytest

from dropcell.model.enums import (
    ClassLocation,
    CoatingType,
    ProtectionMethod,
    SoilCorrosivity,
    SurveyKind,
    TestPointKind,
)


def test_every_coating_declares_a_design_current_density() -> None:
    for coating in CoatingType:
        assert coating.design_current_density_ma_per_m2 > 0


def test_bare_pipe_needs_orders_of_magnitude_more_current_than_epoxy() -> None:
    bare = CoatingType.BARE.design_current_density_ma_per_m2
    fbe = CoatingType.FUSION_BONDED_EPOXY.design_current_density_ma_per_m2
    assert bare / fbe > 100


def test_tape_wrap_and_asphalt_are_the_coatings_that_shield() -> None:
    shielding = {c for c in CoatingType if c.shields_current}
    assert shielding == {CoatingType.TAPE_WRAP, CoatingType.ASPHALT}


def test_bare_pipe_cannot_shield_because_there_is_nothing_to_lift() -> None:
    assert not CoatingType.BARE.shields_current


def test_only_impressed_current_can_be_interrupted() -> None:
    assert ProtectionMethod.IMPRESSED_CURRENT.is_interruptible
    assert not ProtectionMethod.GALVANIC.is_interruptible
    assert not ProtectionMethod.UNPROTECTED.is_interruptible


def test_a_foreign_or_casing_lead_is_not_our_pipe() -> None:
    assert not TestPointKind.FOREIGN.carries_structure_potential
    assert not TestPointKind.CASING.carries_structure_potential
    assert not TestPointKind.ANODE.carries_structure_potential


def test_pipe_coupon_and_isolation_leads_read_our_own_steel() -> None:
    assert TestPointKind.PIPE.carries_structure_potential
    assert TestPointKind.COUPON.carries_structure_potential
    assert TestPointKind.ISOLATION.carries_structure_potential


@pytest.mark.parametrize(
    "kind",
    [SurveyKind.CLOSE_INTERVAL, SurveyKind.DCVG, SurveyKind.ANNUAL],
)
def test_the_surveys_that_need_the_rectifiers_off(kind: SurveyKind) -> None:
    assert kind.needs_interruption


@pytest.mark.parametrize(
    "kind",
    [SurveyKind.SOIL_RESISTIVITY, SurveyKind.RECTIFIER_CHECK, SurveyKind.AC_INTERFERENCE],
)
def test_the_surveys_that_do_not(kind: SurveyKind) -> None:
    assert not kind.needs_interruption


def test_class_location_is_an_integer_one_through_four() -> None:
    assert [int(c) for c in ClassLocation] == [1, 2, 3, 4]
    assert ClassLocation(3) is ClassLocation.SUBURBAN


def test_priority_weight_climbs_with_class_location() -> None:
    weights = [c.priority_weight for c in ClassLocation]
    assert weights == sorted(weights)
    assert ClassLocation.RURAL.priority_weight == pytest.approx(1.0)
    assert ClassLocation.URBAN.priority_weight == pytest.approx(1.75)


def test_corrosivity_bands_round_trip_through_their_values() -> None:
    for band in SoilCorrosivity:
        assert SoilCorrosivity(band.value) is band


def test_the_enums_are_strings_so_they_store_and_print_as_themselves() -> None:
    assert CoatingType.TAPE_WRAP.value == "tape_wrap"
    assert f"{SurveyKind.DCVG}" == "dcvg"
