"""Direct current voltage gradient surveys, which find the holes in the coating.

A close interval survey says the pipe here is under criterion. It does not say
why, and it does not find a bare patch that the protection is still just about
covering. A gradient survey does. With the rectifiers pulsing, a coating defect
draws current out of the soil around it, and that current makes a voltage
gradient in the ground that can be walked over and mapped from the surface.

The size of a defect is not read off the gradient directly. What is read is the
gradient at the defect as a share of the total voltage shift between the two
test posts either side of it, and that share is what everyone calls the percent
IR. A share is used rather than an absolute number because the same hole in wet
clay and in dry sand produces completely different millivolts, and neither of
those figures says anything about how much steel is exposed.

The share is then banded, and the band is what drives a dig. The bands are
coarse on purpose. Nobody can size a defect from the surface, and pretending
otherwise puts crews on the wrong holes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import IntEnum

from dropcell.errors import ValidationError
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station


class DcvgCategory(IntEnum):
    """The four bands a percent IR falls into."""

    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4

    @property
    def label(self) -> str:
        """What the band is called on a report."""
        return _CATEGORY_LABEL[self]

    @property
    def response_days(self) -> int | None:
        """How long the operator has before this one has to be dealt with."""
        return _RESPONSE_DAYS[self]

    @property
    def is_immediate(self) -> bool:
        """Whether a dig is scheduled without waiting for anything else."""
        return self is DcvgCategory.FOUR


_CATEGORY_LABEL: dict[DcvgCategory, str] = {
    DcvgCategory.ONE: "minor, monitor at the next survey",
    DcvgCategory.TWO: "moderate, schedule with other work",
    DcvgCategory.THREE: "major, schedule on its own",
    DcvgCategory.FOUR: "severe, dig without waiting",
}

_RESPONSE_DAYS: dict[DcvgCategory, int | None] = {
    DcvgCategory.ONE: None,
    DcvgCategory.TWO: 365,
    DcvgCategory.THREE: 180,
    DcvgCategory.FOUR: 30,
}

CATEGORY_BANDS: list[tuple[float, DcvgCategory]] = [
    (16.0, DcvgCategory.ONE),
    (36.0, DcvgCategory.TWO),
    (71.0, DcvgCategory.THREE),
]


def classify_percent_ir(percent_ir: float) -> DcvgCategory:
    """Put a percent IR into its band."""
    if not 0.0 <= percent_ir <= 100.0:
        raise ValidationError("percent IR is a share of the shift", percent_ir=percent_ir)
    for limit, category in CATEGORY_BANDS:
        if percent_ir < limit:
            return category
    return DcvgCategory.FOUR


@dataclass(frozen=True)
class DcvgIndication:
    """One defect found on a gradient survey."""

    line_code: str
    station: Station
    gradient_mv: float
    section_shift_mv: float
    found_on: dt.date
    anodic: bool = False
    remark: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if self.gradient_mv < 0:
            raise ValidationError(
                "a gradient is measured as a magnitude", gradient_mv=self.gradient_mv
            )
        if self.section_shift_mv <= 0:
            raise ValidationError(
                "the section shift has to be positive",
                section_shift_mv=self.section_shift_mv,
            )
        if self.gradient_mv > self.section_shift_mv:
            raise ValidationError(
                "a defect cannot draw more gradient than the whole section shifted",
                gradient_mv=self.gradient_mv,
                section_shift_mv=self.section_shift_mv,
            )

    @property
    def percent_ir(self) -> float:
        """The gradient as a share of the section shift."""
        return 100.0 * self.gradient_mv / self.section_shift_mv

    @property
    def category(self) -> DcvgCategory:
        """The band this indication falls in."""
        return classify_percent_ir(self.percent_ir)

    @property
    def due_by(self) -> dt.date | None:
        """When this one has to be dealt with, if there is a date at all."""
        days = self.category.response_days
        return None if days is None else self.found_on + dt.timedelta(days=days)


def rank_indications(indications: list[DcvgIndication]) -> list[DcvgIndication]:
    """Order a survey's findings worst first, then by where they are."""
    return sorted(
        indications,
        key=lambda item: (-item.percent_ir, item.station.metres),
    )


def anodic_indications(indications: list[DcvgIndication]) -> list[DcvgIndication]:
    """Only the defects where current is leaving the pipe.

    An anodic indication is not a coating fault the protection is covering. It
    is steel actively giving up metal, usually because the defect sits in a
    stray current field, and it outranks a larger cathodic defect however the
    percent IR compares.
    """
    return [item for item in indications if item.anodic]
