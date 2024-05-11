from __future__ import annotations

import pytest

from dropcell.model.enums import ClassLocation, CoatingType, ProtectionMethod
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange


@pytest.fixture
def segment() -> Segment:
    return Segment(
        code="AL-2-004",
        line_code="AL-2",
        extent=StationRange(Station(0.0), Station(1200.0)),
        coating=CoatingType.COAL_TAR,
        protection=ProtectionMethod.IMPRESSED_CURRENT,
        class_location=ClassLocation.RURAL,
        outside_diameter_mm=323.9,
        wall_thickness_mm=6.35,
        installed_year=1974,
    )
