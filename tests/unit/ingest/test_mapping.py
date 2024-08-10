from __future__ import annotations

import pytest

from dropcell.errors import IngestError, ValidationError
from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile, fold_header


def column(**overrides: object) -> ColumnMapping:
    kwargs: dict[str, object] = {
        "field_name": "station",
        "field_type": FieldType.STATION,
        "headers": ("Station", "Chainage"),
    }
    kwargs.update(overrides)
    return ColumnMapping(**kwargs)  # type: ignore[arg-type]


def profile(**overrides: object) -> MappingProfile:
    kwargs: dict[str, object] = {
        "name": "acme_cis",
        "columns": (
            column(),
            column(field_name="on_mv", field_type=FieldType.POTENTIAL, headers=("P/S On",)),
            column(
                field_name="off_mv",
                field_type=FieldType.POTENTIAL,
                headers=("P/S Off", "Instant Off"),
                required=False,
            ),
        ),
    }
    kwargs.update(overrides)
    return MappingProfile(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("Station", "station"),
        ("  STATION  ", "station"),
        ("P/S On", "pson"),
        ("on_potential_mv", "onpotentialmv"),
        ("Off Potential (mV)", "offpotential"),
        ("chain-age", "chainage"),
    ],
)
def test_folding_removes_the_noise_a_person_adds(raw: str, folded: str) -> None:
    assert fold_header(raw) == folded


def test_a_column_answers_to_any_of_its_headers() -> None:
    made = column()
    assert made.matches("station")
    assert made.matches("CHAINAGE")
    assert made.matches("Chain_Age")
    assert not made.matches("distance")


def test_a_column_with_no_field_name_is_refused() -> None:
    with pytest.raises(ValidationError):
        column(field_name="  ")


def test_a_column_with_no_headers_is_refused() -> None:
    with pytest.raises(ValidationError):
        column(headers=())


def test_a_required_column_cannot_have_a_default() -> None:
    with pytest.raises(ValidationError):
        column(default="0")


def test_an_optional_column_can() -> None:
    assert column(required=False, default="0").default == "0"


def test_a_profile_with_no_columns_is_refused() -> None:
    with pytest.raises(ValidationError):
        profile(columns=())


def test_two_columns_mapping_to_one_field_are_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        profile(columns=(column(), column(headers=("Distance",))))
    assert caught.value.detail["field"] == "station"


def test_skipping_a_negative_number_of_rows_is_refused() -> None:
    with pytest.raises(ValidationError):
        profile(skip_rows=-1)


def test_the_required_fields_are_the_ones_marked_required() -> None:
    assert profile().required_fields == ("station", "on_mv")


def test_a_column_can_be_fetched_by_field_name() -> None:
    assert profile().column("on_mv").field_type is FieldType.POTENTIAL


def test_an_unknown_field_name_lists_the_ones_that_exist() -> None:
    with pytest.raises(ValidationError) as caught:
        profile().column("wishful")
    assert "station" in caught.value.detail["known"]


def test_resolving_finds_the_position_of_every_column() -> None:
    positions = profile().resolve(["Station", "P/S On", "P/S Off"])
    assert positions == {"station": 0, "on_mv": 1, "off_mv": 2}


def test_resolving_does_not_care_about_column_order() -> None:
    positions = profile().resolve(["P/S Off", "P/S On", "CHAINAGE"])
    assert positions == {"off_mv": 0, "on_mv": 1, "station": 2}


def test_an_optional_column_that_is_absent_is_simply_not_there() -> None:
    positions = profile().resolve(["Station", "P/S On"])
    assert "off_mv" not in positions


def test_a_missing_required_column_names_itself_and_what_was_found() -> None:
    with pytest.raises(IngestError) as caught:
        profile().resolve(["Station", "Remark"])
    assert caught.value.detail["missing"] == ["on_mv"]
    assert caught.value.detail["found"] == ["Station", "Remark"]


def test_a_column_appearing_twice_takes_the_first_position() -> None:
    positions = profile().resolve(["Station", "P/S On", "Chainage"])
    assert positions["station"] == 0


def test_the_second_alias_of_an_optional_column_is_matched_too() -> None:
    positions = profile().resolve(["Station", "P/S On", "Instant Off"])
    assert positions["off_mv"] == 2
