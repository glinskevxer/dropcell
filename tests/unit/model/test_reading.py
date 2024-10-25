from __future__ import annotations

import datetime as dt

import pytest

from dropcell.electrodes import Electrode
from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.reading import Reading, check_potential


def make_reading(**overrides: object) -> Reading:
    kwargs: dict[str, object] = {
        "test_point_code": "TP-114",
        "lead": LeadKind.PIPE,
        "taken_on": dt.date(2025, 3, 14),
        "on_mv": -1120.0,
    }
    kwargs.update(overrides)
    return Reading(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [-3000.0, 0.0, 1000.0])
def test_a_plausible_potential_passes_the_check(value: float) -> None:
    assert check_potential(value, "on potential") == value


@pytest.mark.parametrize("value", [-3000.1, 1000.1, -12000.0])
def test_an_impossible_potential_is_refused(value: float) -> None:
    with pytest.raises(ValidationError):
        check_potential(value, "on potential")


def test_a_reading_refuses_an_impossible_on_potential() -> None:
    with pytest.raises(ValidationError):
        make_reading(on_mv=-9000.0)


def test_a_reading_refuses_an_impossible_off_or_native_potential() -> None:
    with pytest.raises(ValidationError):
        make_reading(off_mv=-9000.0)
    with pytest.raises(ValidationError):
        make_reading(native_mv=4000.0)


def test_a_reading_without_an_off_is_not_interrupted() -> None:
    reading = make_reading()
    assert not reading.is_interrupted
    assert reading.ir_drop_mv is None
    assert reading.off_cse_mv is None


def test_ir_drop_is_the_gap_between_on_and_off() -> None:
    reading = make_reading(on_mv=-1120.0, off_mv=-905.0)
    assert reading.is_interrupted
    assert reading.ir_drop_mv == pytest.approx(-215.0)


def test_polarisation_needs_both_an_off_and_a_native_potential() -> None:
    assert make_reading(off_mv=-905.0).polarisation_mv is None
    assert make_reading(native_mv=-580.0).polarisation_mv is None
    reading = make_reading(off_mv=-905.0, native_mv=-580.0)
    assert reading.polarisation_mv == pytest.approx(325.0)


def test_a_reading_taken_against_calomel_restates_against_copper_sulfate() -> None:
    reading = make_reading(on_mv=-1043.0, off_mv=-828.0, electrode=Electrode.SCE)
    assert reading.on_cse_mv == pytest.approx(-1120.0)
    assert reading.off_cse_mv == pytest.approx(-905.0)


def test_the_comment_stays_out_of_equality() -> None:
    assert make_reading(comment="dog on the gate") == make_reading()
