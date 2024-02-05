from __future__ import annotations

import pytest

from dropcell.errors import (
    ConflictError,
    DropcellError,
    IngestError,
    MigrationError,
    NotFoundError,
    PolicyError,
    StationError,
    StoreError,
    UnitError,
    ValidationError,
)


def test_bare_error_stringifies_to_the_message() -> None:
    err = DropcellError("something went sideways")
    assert str(err) == "something went sideways"
    assert err.detail == {}


def test_detail_is_appended_in_sorted_key_order() -> None:
    err = DropcellError("bad reading", station="12+450", line="AL-2")
    assert str(err) == "bad reading (line='AL-2', station='12+450')"


def test_as_dict_carries_code_message_and_a_copy_of_detail() -> None:
    err = ValidationError("out of range", value=-2100)
    payload = err.as_dict()
    assert payload == {
        "code": "validation",
        "message": "out of range",
        "detail": {"value": -2100},
    }
    payload["detail"]["value"] = 0
    assert err.detail["value"] == -2100


@pytest.mark.parametrize(
    ("cls", "code"),
    [
        (DropcellError, "dropcell_error"),
        (ValidationError, "validation"),
        (UnitError, "unit"),
        (StationError, "station"),
        (NotFoundError, "not_found"),
        (ConflictError, "conflict"),
        (PolicyError, "policy"),
        (IngestError, "ingest"),
        (StoreError, "store"),
        (MigrationError, "migration"),
    ],
)
def test_every_error_declares_its_own_code(cls: type[DropcellError], code: str) -> None:
    assert cls.code == code


def test_unit_and_station_errors_are_validation_errors() -> None:
    assert issubclass(UnitError, ValidationError)
    assert issubclass(StationError, ValidationError)
    assert not issubclass(NotFoundError, ValidationError)


def test_migration_error_is_a_store_error() -> None:
    assert issubclass(MigrationError, StoreError)


def test_ingest_error_folds_the_row_number_into_detail() -> None:
    err = IngestError("column missing", row=41, column="off_mv")
    assert err.row == 41
    assert err.detail == {"row": 41, "column": "off_mv"}
    assert "row=41" in str(err)


def test_ingest_error_without_a_row_leaves_detail_alone() -> None:
    err = IngestError("file is empty", path="cis-2025-03.csv")
    assert err.row is None
    assert err.detail == {"path": "cis-2025-03.csv"}


def test_every_error_can_be_caught_as_the_base_class() -> None:
    with pytest.raises(DropcellError):
        raise MigrationError("schema 7 on disk, 9 expected")
