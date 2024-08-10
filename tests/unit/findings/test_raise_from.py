from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.findings.finding import FindingKind
from dropcell.findings.raise_from import (
    format_code,
    from_casing,
    from_cis_sections,
    from_dcvg,
    next_sequence,
)
from dropcell.interference.casing import CasingAssessment, CasingStatus
from dropcell.stationing import Station, StationRange
from dropcell.survey.dcvg import DcvgIndication
from dropcell.survey.sections import UnderCriterionSection

RAISED = dt.date(2025, 3, 14)


def section(worst: float, start: float = 1200.0, end: float = 1260.0) -> UnderCriterionSection:
    return UnderCriterionSection(
        extent=StationRange(Station(start), Station(end)),
        readings=40,
        worst_off_mv=worst,
        mean_off_mv=worst - 10.0,
        threshold_mv=-850.0,
    )


def indication(gradient: float = 40.0, **overrides: object) -> DcvgIndication:
    kwargs: dict[str, object] = {
        "line_code": "AL-2",
        "station": Station(1245.5),
        "gradient_mv": gradient,
        "section_shift_mv": 400.0,
        "found_on": RAISED,
    }
    kwargs.update(overrides)
    return DcvgIndication(**kwargs)  # type: ignore[arg-type]


def test_the_first_finding_of_a_year_is_number_one() -> None:
    assert next_sequence([], 2025) == 1
    assert format_code(2025, 1) == "F-2025-001"


def test_a_sequence_carries_on_from_what_is_already_stored() -> None:
    assert next_sequence(["F-2025-001", "F-2025-014"], 2025) == 15


def test_last_year_numbers_do_not_move_this_year_on() -> None:
    assert next_sequence(["F-2024-114"], 2025) == 1


def test_codes_that_are_not_finding_codes_are_ignored() -> None:
    assert next_sequence(["TP-114", "F-2025-x", ""], 2025) == 1


def test_a_sequence_below_one_is_refused() -> None:
    with pytest.raises(ValidationError):
        format_code(2025, 0)


def test_one_finding_comes_out_of_each_section() -> None:
    made = from_cis_sections(
        [section(-800.0), section(-820.0, 2000.0, 2100.0)],
        line_code="AL-2",
        raised_on=RAISED,
        source="cis-2025-03.csv",
    )
    assert [item.code for item in made] == ["F-2025-001", "F-2025-002"]
    assert all(item.kind is FindingKind.UNDER_CRITERION for item in made)


def test_a_section_finding_keeps_the_extent_it_came_from() -> None:
    made = from_cis_sections(
        [section(-800.0)], line_code="AL-2", raised_on=RAISED, source="cis.csv"
    )
    assert made[0].extent == StationRange(Station(1200.0), Station(1260.0))
    assert made[0].source == "cis.csv"


def test_a_severe_section_is_due_sooner_than_a_minor_one() -> None:
    severe = from_cis_sections(
        [section(-700.0)], line_code="AL-2", raised_on=RAISED, source="cis.csv"
    )[0]
    minor = from_cis_sections(
        [section(-840.0)], line_code="AL-2", raised_on=RAISED, source="cis.csv"
    )[0]
    assert severe.due_by is not None
    assert minor.due_by is not None
    assert severe.due_by < minor.due_by


def test_the_summary_carries_the_length_and_the_worst_reading() -> None:
    made = from_cis_sections(
        [section(-800.0)], line_code="AL-2", raised_on=RAISED, source="cis.csv"
    )[0]
    assert "60 m under criterion" in made.summary
    assert "-800 mV" in made.summary


def test_section_codes_carry_on_from_the_existing_register() -> None:
    made = from_cis_sections(
        [section(-800.0)],
        line_code="AL-2",
        raised_on=RAISED,
        source="cis.csv",
        existing_codes=["F-2025-007"],
    )
    assert made[0].code == "F-2025-008"


def test_a_cathodic_indication_becomes_a_coating_defect() -> None:
    made = from_dcvg([indication()], raised_on=RAISED, source="dcvg.csv")
    assert made[0].kind is FindingKind.COATING_DEFECT
    assert "10 percent IR" in made[0].summary


def test_an_anodic_indication_becomes_an_interference_finding() -> None:
    made = from_dcvg([indication(anodic=True)], raised_on=RAISED, source="dcvg.csv")
    assert made[0].kind is FindingKind.INTERFERENCE
    assert "leaving the pipe" in made[0].summary


def test_a_defect_finding_is_given_a_length_so_it_is_not_a_point() -> None:
    made = from_dcvg([indication()], raised_on=RAISED, source="dcvg.csv")
    assert made[0].length_m == pytest.approx(1.0)
    longer = from_dcvg([indication()], raised_on=RAISED, source="dcvg.csv", defect_length_m=4.0)
    assert longer[0].length_m == pytest.approx(4.0)


def test_a_defect_length_of_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        from_dcvg([indication()], raised_on=RAISED, source="d.csv", defect_length_m=0.0)


def test_the_dcvg_due_date_comes_off_the_category() -> None:
    severe = from_dcvg([indication(gradient=380.0)], raised_on=RAISED, source="d.csv")[0]
    assert severe.due_by == dt.date(2025, 4, 13)
    minor = from_dcvg([indication(gradient=20.0)], raised_on=RAISED, source="d.csv")[0]
    assert minor.due_by is None


def assessment(status: CasingStatus, code: str = "CS-12") -> CasingAssessment:
    return CasingAssessment(
        casing_code=code,
        status=status,
        separation_mv=4.0,
        reason="pipe and casing read as one structure",
        tested_on=RAISED,
    )


def test_a_clear_casing_raises_nothing() -> None:
    made = from_casing(
        [assessment(CasingStatus.CLEAR)],
        line_code="AL-2",
        stations={"CS-12": Station(1245.5)},
        source="casing.csv",
    )
    assert made == []


def test_a_shorted_casing_raises_a_finding() -> None:
    made = from_casing(
        [assessment(CasingStatus.METALLIC_SHORT)],
        line_code="AL-2",
        stations={"CS-12": Station(1245.5)},
        source="casing.csv",
    )
    assert made[0].kind is FindingKind.SHORTED_CASING
    assert made[0].length_m == pytest.approx(20.0)
    assert "metallic_short" in made[0].summary


def test_an_indeterminate_casing_raises_one_too() -> None:
    made = from_casing(
        [assessment(CasingStatus.INDETERMINATE)],
        line_code="AL-2",
        stations={"CS-12": Station(1245.5)},
        source="casing.csv",
    )
    assert len(made) == 1


def test_a_casing_with_no_known_station_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        from_casing(
            [assessment(CasingStatus.METALLIC_SHORT)],
            line_code="AL-2",
            stations={},
            source="casing.csv",
        )
    assert caught.value.detail["casing_code"] == "CS-12"


def test_casing_findings_number_on_from_the_register_too() -> None:
    made = from_casing(
        [
            assessment(CasingStatus.METALLIC_SHORT, "CS-12"),
            assessment(CasingStatus.ELECTROLYTIC, "CS-13"),
        ],
        line_code="AL-2",
        stations={"CS-12": Station(1245.5), "CS-13": Station(4000.0)},
        source="casing.csv",
        existing_codes=["F-2025-004"],
    )
    assert [item.code for item in made] == ["F-2025-005", "F-2025-006"]
