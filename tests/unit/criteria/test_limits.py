from __future__ import annotations

import dataclasses

import pytest

from dropcell.criteria.base import Evidence, Outcome
from dropcell.criteria.limits import (
    DISBONDMENT_LIMIT_MV,
    SHIELDING_COATING_LIMIT_MV,
    IrDropShareLimit,
    OverProtectionLimit,
    disbondment_limit_mv,
)
from dropcell.model.enums import CoatingType
from dropcell.model.segment import Segment


def evidence(segment: Segment, **overrides: object) -> Evidence:
    return Evidence(segment=segment, **overrides)  # type: ignore[arg-type]


def test_a_shielding_coating_has_the_tighter_limit() -> None:
    assert disbondment_limit_mv(CoatingType.TAPE_WRAP) == pytest.approx(
        SHIELDING_COATING_LIMIT_MV
    )
    assert disbondment_limit_mv(CoatingType.FUSION_BONDED_EPOXY) == pytest.approx(
        DISBONDMENT_LIMIT_MV
    )


def test_an_ordinary_reading_sits_inside_the_limit(segment: Segment) -> None:
    result = OverProtectionLimit().assess(evidence(segment, off_mv=-905.0))
    assert result.outcome is Outcome.MET
    assert result.note == ""


def test_a_reading_past_the_limit_is_exceeded(segment: Segment) -> None:
    result = OverProtectionLimit().assess(evidence(segment, off_mv=-1310.0))
    assert result.outcome is Outcome.EXCEEDED
    assert result.margin_mv == pytest.approx(-110.0)
    assert result.detail["limit_mv"] == pytest.approx(DISBONDMENT_LIMIT_MV)


def test_a_reading_exactly_on_the_limit_is_inside_it(segment: Segment) -> None:
    result = OverProtectionLimit().assess(evidence(segment, off_mv=-1200.0))
    assert result.outcome is Outcome.MET


def test_the_same_reading_breaks_the_limit_on_a_tape_wrapped_segment(
    segment: Segment,
) -> None:
    limit = OverProtectionLimit()
    taped = dataclasses.replace(segment, coating=CoatingType.TAPE_WRAP)
    reading = -1150.0
    assert limit.assess(evidence(segment, off_mv=reading)).outcome is Outcome.MET
    assert limit.assess(evidence(taped, off_mv=reading)).outcome is Outcome.EXCEEDED


def test_a_point_that_passes_a_criterion_can_still_break_the_limit(
    segment: Segment,
) -> None:
    from dropcell.criteria.potential import PolarisedPotentialCriterion

    reading = evidence(segment, off_mv=-1420.0)
    assert PolarisedPotentialCriterion().assess(reading).outcome is Outcome.MET
    assert OverProtectionLimit().assess(reading).outcome is Outcome.EXCEEDED


def test_the_limit_needs_a_polarised_potential(segment: Segment) -> None:
    limit = OverProtectionLimit()
    assert not limit.applies_to(evidence(segment, on_mv=-1120.0))
    assert limit.assess(evidence(segment)).outcome is Outcome.NOT_ASSESSED


def test_a_small_ir_drop_is_inside_the_share_limit(segment: Segment) -> None:
    result = IrDropShareLimit().assess(evidence(segment, on_mv=-1120.0, off_mv=-905.0))
    assert result.outcome is Outcome.MET
    assert result.detail["share"] == pytest.approx(215.0 / 1120.0)


def test_a_reading_that_is_mostly_soil_drop_is_flagged(segment: Segment) -> None:
    result = IrDropShareLimit().assess(evidence(segment, on_mv=-1800.0, off_mv=-820.0))
    assert result.outcome is Outcome.EXCEEDED
    assert "soil drop" in result.note


def test_the_share_limit_can_be_moved(segment: Segment) -> None:
    strict = IrDropShareLimit(share_limit=0.1)
    result = strict.assess(evidence(segment, on_mv=-1120.0, off_mv=-905.0))
    assert result.outcome is Outcome.EXCEEDED


def test_the_share_limit_needs_both_potentials(segment: Segment) -> None:
    limit = IrDropShareLimit()
    assert not limit.applies_to(evidence(segment, on_mv=-1120.0))
    assert limit.assess(evidence(segment, on_mv=-1120.0)).detail["missing"] == ["off_mv"]


def test_a_zero_on_potential_cannot_be_divided_into(segment: Segment) -> None:
    result = IrDropShareLimit().assess(evidence(segment, on_mv=0.0, off_mv=-10.0))
    assert result.outcome is Outcome.NOT_ASSESSED
