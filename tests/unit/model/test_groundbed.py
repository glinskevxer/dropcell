from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.model.enums import AnodeMaterial, GroundbedKind
from dropcell.model.groundbed import Groundbed


def make_bed(**overrides: object) -> Groundbed:
    kwargs: dict[str, object] = {
        "code": "GB-3",
        "kind": GroundbedKind.DEEP_WELL,
        "material": AnodeMaterial.HIGH_SILICON_IRON,
        "anode_count": 10,
        "anode_mass_kg": 20.0,
        "installed_on": dt.date(2004, 9, 1),
        "design_current_a": 15.0,
    }
    kwargs.update(overrides)
    return Groundbed(**kwargs)  # type: ignore[arg-type]


def test_the_code_is_normalised() -> None:
    assert make_bed(code="gb 3").code == "GB-3"


def test_a_bed_needs_anodes_with_mass_and_a_design_current() -> None:
    with pytest.raises(ValidationError):
        make_bed(anode_count=0)
    with pytest.raises(ValidationError):
        make_bed(anode_mass_kg=0.0)
    with pytest.raises(ValidationError):
        make_bed(design_current_a=0.0)


@pytest.mark.parametrize("utilisation", [0.0, -0.1, 1.4])
def test_utilisation_has_to_be_a_fraction(utilisation: float) -> None:
    with pytest.raises(ValidationError):
        make_bed(utilisation=utilisation)


def test_a_galvanic_string_of_graphite_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        make_bed(kind=GroundbedKind.GALVANIC_STRING, material=AnodeMaterial.GRAPHITE)
    assert caught.value.detail["material"] == "graphite"


def test_a_galvanic_string_of_magnesium_is_fine() -> None:
    bed = make_bed(kind=GroundbedKind.GALVANIC_STRING, material=AnodeMaterial.MAGNESIUM)
    assert bed.is_galvanic


def test_installed_mass_is_the_count_times_the_anode() -> None:
    assert make_bed().installed_mass_kg == pytest.approx(200.0)


def test_only_the_utilisation_fraction_can_be_spent() -> None:
    assert make_bed().usable_mass_kg == pytest.approx(170.0)
    assert make_bed(utilisation=1.0).usable_mass_kg == pytest.approx(200.0)


def test_consumption_follows_the_material_rate() -> None:
    assert make_bed().consumption_kg(10.0) == pytest.approx(4.5)
    zinc = make_bed(kind=GroundbedKind.GALVANIC_STRING, material=AnodeMaterial.ZINC)
    assert zinc.consumption_kg(10.0) == pytest.approx(119.0)


def test_negative_ampere_years_are_refused() -> None:
    with pytest.raises(ValidationError):
        make_bed().consumption_kg(-1.0)


def test_remaining_mass_falls_as_the_bed_works_and_stops_at_nothing() -> None:
    bed = make_bed()
    assert bed.remaining_mass_kg(0.0) == pytest.approx(170.0)
    assert bed.remaining_mass_kg(100.0) == pytest.approx(125.0)
    assert bed.remaining_mass_kg(100_000.0) == pytest.approx(0.0)


def test_the_spent_fraction_is_capped_at_all_of_it() -> None:
    bed = make_bed()
    assert bed.spent_fraction(0.0) == pytest.approx(0.0)
    assert bed.spent_fraction(377.78) == pytest.approx(1.0, abs=1e-3)
    assert bed.spent_fraction(9_999.0) == pytest.approx(1.0)


def test_design_life_is_the_usable_mass_over_the_design_current() -> None:
    assert make_bed().design_life_years() == pytest.approx(170.0 / (15.0 * 0.45))


def test_a_mixed_metal_oxide_bed_outlives_everything_else() -> None:
    mmo = make_bed(material=AnodeMaterial.MIXED_METAL_OXIDE)
    assert mmo.design_life_years() > make_bed().design_life_years() * 1000


def test_remaining_life_accounts_for_what_the_bed_has_already_passed() -> None:
    bed = make_bed()
    fresh = bed.remaining_life_years(0.0, 15.0)
    used = bed.remaining_life_years(100.0, 15.0)
    assert used < fresh
    assert used == pytest.approx(125.0 / (15.0 * 0.45))


def test_remaining_life_at_a_higher_output_is_shorter() -> None:
    bed = make_bed()
    assert bed.remaining_life_years(0.0, 30.0) == pytest.approx(
        bed.remaining_life_years(0.0, 15.0) / 2
    )


def test_remaining_life_at_no_current_is_refused_rather_than_infinite() -> None:
    with pytest.raises(ValidationError):
        make_bed().remaining_life_years(0.0, 0.0)


def test_a_bed_is_finished_once_most_of_the_usable_metal_has_gone() -> None:
    bed = make_bed()
    assert not bed.is_end_of_life(300.0)
    assert bed.is_end_of_life(340.0)


def test_remote_beds_are_the_ones_in_a_hole_of_their_own() -> None:
    assert GroundbedKind.DEEP_WELL.is_remote
    assert GroundbedKind.SHALLOW_HORIZONTAL.is_remote
    assert not GroundbedKind.DISTRIBUTED.is_remote
    assert not GroundbedKind.GALVANIC_STRING.is_remote


def test_only_the_galvanic_materials_carry_a_driving_potential() -> None:
    assert AnodeMaterial.MAGNESIUM.driving_potential_mv == pytest.approx(-1550.0)
    assert AnodeMaterial.ZINC.driving_potential_mv == pytest.approx(-1100.0)
    assert AnodeMaterial.GRAPHITE.driving_potential_mv is None
    assert not AnodeMaterial.GRAPHITE.is_galvanic
