from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.interference.isolation import (
    IsolationJoint,
    IsolationStatus,
    IsolationTest,
    JointKind,
    classify_isolation,
)
from dropcell.stationing import Station


def joint(**overrides: object) -> IsolationJoint:
    kwargs: dict[str, object] = {
        "code": "IJ-2",
        "line_code": "AL-2",
        "station": Station(120.0),
        "kind": JointKind.MONOLITHIC,
        "separates": "Ashfield compressor station",
        "installed_on": dt.date(2004, 9, 1),
    }
    kwargs.update(overrides)
    return IsolationJoint(**kwargs)  # type: ignore[arg-type]


def isolation_test(**overrides: object) -> IsolationTest:
    kwargs: dict[str, object] = {
        "joint_code": "IJ-2",
        "tested_on": dt.date(2025, 3, 14),
        "our_side_mv": -1120.0,
        "other_side_mv": -420.0,
    }
    kwargs.update(overrides)
    return IsolationTest(**kwargs)  # type: ignore[arg-type]


def test_codes_are_normalised_and_the_other_side_is_trimmed() -> None:
    made = joint(code="ij 2", line_code="al-2", separates="  the station  ")
    assert (made.code, made.line_code) == ("IJ-2", "AL-2")
    assert made.separates == "the station"


def test_a_joint_that_separates_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        joint(separates="  ")


def test_only_a_welded_joint_has_to_be_cut_out() -> None:
    assert not JointKind.MONOLITHIC.is_serviceable
    assert JointKind.FLANGE_KIT.is_serviceable
    assert JointKind.ISOLATING_UNION.is_serviceable


def test_two_sides_far_apart_are_isolating() -> None:
    result = classify_isolation(isolation_test())
    assert result.status is IsolationStatus.ISOLATING
    assert result.separation_mv == pytest.approx(700.0)
    assert result.due_by is None
    assert not result.status.needs_work


def test_two_sides_that_read_the_same_are_shorted() -> None:
    result = classify_isolation(isolation_test(other_side_mv=-1112.0))
    assert result.status is IsolationStatus.SHORTED
    assert result.due_by == dt.date(2025, 4, 28)


def test_something_bridging_the_joint_reads_partial() -> None:
    result = classify_isolation(isolation_test(other_side_mv=-1060.0))
    assert result.status is IsolationStatus.PARTIAL
    assert "bridging" in result.reason
    assert result.due_by == dt.date(2025, 9, 10)


def test_a_short_reading_with_a_surge_protector_in_place_proves_nothing() -> None:
    protected = joint(surge_protector_fitted=True)
    result = classify_isolation(isolation_test(other_side_mv=-1112.0), protected)
    assert result.status is IsolationStatus.PARTIAL
    assert "proves nothing" in result.reason


def test_the_same_reading_with_the_protector_lifted_is_a_short() -> None:
    protected = joint(surge_protector_fitted=True)
    result = classify_isolation(
        isolation_test(other_side_mv=-1112.0, surge_protector_removed=True), protected
    )
    assert result.status is IsolationStatus.SHORTED


def test_a_joint_with_no_protector_needs_no_special_case() -> None:
    result = classify_isolation(isolation_test(other_side_mv=-1112.0), joint())
    assert result.status is IsolationStatus.SHORTED


def test_a_test_read_without_the_joint_record_is_still_readable() -> None:
    assert classify_isolation(isolation_test()).status is IsolationStatus.ISOLATING


def test_the_bands_can_be_moved() -> None:
    reading = isolation_test(other_side_mv=-1060.0)
    assert classify_isolation(reading).status is IsolationStatus.PARTIAL
    wide = classify_isolation(reading, shorted_mv=80.0, partial_mv=200.0)
    assert wide.status is IsolationStatus.SHORTED


def test_bands_that_overlap_are_refused() -> None:
    with pytest.raises(ValidationError):
        classify_isolation(isolation_test(), shorted_mv=200.0, partial_mv=50.0)
    with pytest.raises(ValidationError):
        classify_isolation(isolation_test(), shorted_mv=0.0)


def test_an_impossible_potential_is_refused() -> None:
    with pytest.raises(ValidationError):
        isolation_test(our_side_mv=-9000.0)
    with pytest.raises(ValidationError):
        isolation_test(other_side_mv=4000.0)


def test_a_shorted_joint_is_looked_at_sooner_than_a_partial_one() -> None:
    assert IsolationStatus.SHORTED.response_days == 45
    assert IsolationStatus.PARTIAL.response_days == 180
    assert IsolationStatus.ISOLATING.response_days is None
