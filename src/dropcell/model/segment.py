"""A stretch of one line that shares a coating, a protection method and a class.

Segmentation is how a line stops being one number. Coating changes at a road
bore, class location changes when a housing estate arrives, protection changes
where a galvanic string was dropped in beside an impressed current system. The
segment is the smallest piece a criterion is applied to as a whole.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

from dropcell.errors import ValidationError
from dropcell.model.enums import ClassLocation, CoatingType, ProtectionMethod, SoilCorrosivity
from dropcell.model.ids import normalise_code
from dropcell.model.line import EARLIEST_INSTALL_YEAR
from dropcell.soil import classify_corrosivity
from dropcell.stationing import Station, StationRange


@dataclass(frozen=True)
class Segment:
    """One homogeneous piece of pipe."""

    code: str
    line_code: str
    extent: StationRange
    coating: CoatingType
    protection: ProtectionMethod
    class_location: ClassLocation
    outside_diameter_mm: float
    wall_thickness_mm: float
    installed_year: int
    depth_of_cover_m: float = 1.2
    soil_resistivity_ohm_m: float | None = None
    notes: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="segment code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        if self.extent.length_m <= 0:
            raise ValidationError("segment must cover some line", code=self.code)
        if self.outside_diameter_mm <= 0:
            raise ValidationError("segment diameter must be positive", code=self.code)
        if not 0 < self.wall_thickness_mm < self.outside_diameter_mm / 2:
            raise ValidationError(
                "wall thickness has to fit inside the pipe",
                code=self.code,
                wall_mm=self.wall_thickness_mm,
                outside_diameter_mm=self.outside_diameter_mm,
            )
        if self.depth_of_cover_m <= 0:
            raise ValidationError("depth of cover must be positive", code=self.code)
        if not EARLIEST_INSTALL_YEAR <= self.installed_year <= dt.date.today().year:
            raise ValidationError(
                "install year is outside the range a pipeline can have",
                code=self.code,
                year=self.installed_year,
            )
        if self.soil_resistivity_ohm_m is not None and self.soil_resistivity_ohm_m <= 0:
            raise ValidationError(
                "soil resistivity must be positive when it is given",
                code=self.code,
                value=self.soil_resistivity_ohm_m,
            )

    @property
    def length_m(self) -> float:
        """How much line the segment covers."""
        return self.extent.length_m

    @property
    def external_area_m2(self) -> float:
        """Outside surface of the steel, which is what has to be polarised."""
        return math.pi * (self.outside_diameter_mm / 1000.0) * self.length_m

    @property
    def design_current_ma(self) -> float:
        """Current the coating is expected to draw over the whole segment."""
        return self.coating.design_current_density_ma_per_m2 * self.external_area_m2

    @property
    def corrosivity(self) -> SoilCorrosivity | None:
        """Soil band, when a resistivity has been measured here."""
        if self.soil_resistivity_ohm_m is None:
            return None
        return classify_corrosivity(self.soil_resistivity_ohm_m)

    @property
    def needs_above_ground_survey(self) -> bool:
        """Whether potentials at posts are not enough evidence for this segment.

        A shielding coating can hide corroding steel from both the current and
        the reading, so the segment has to be walked with a close interval or
        gradient survey instead of trusted to its test points.
        """
        return self.coating.shields_current

    @property
    def is_protected_by_design(self) -> bool:
        """Whether anything is meant to be pushing current onto this pipe."""
        return self.protection is not ProtectionMethod.UNPROTECTED

    def contains(self, station: Station) -> bool:
        """Whether a station falls on this segment."""
        return self.extent.contains(station)

    def overlaps(self, other: Segment) -> bool:
        """Whether two segments of the same line cover any common pipe."""
        return self.line_code == other.line_code and self.extent.overlaps(other.extent)
