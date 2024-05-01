from __future__ import annotations

import datetime as dt

import pytest

from dropcell.model.enums import ClassLocation, CoatingType, Commodity, ProtectionMethod
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.migrations import migrate


@pytest.fixture
def database() -> Database:
    store = Database(":memory:")
    migrate(store, now=dt.datetime(2025, 3, 14, tzinfo=dt.UTC))
    return store


@pytest.fixture
def line() -> Line:
    return Line(
        code="AL-2",
        name="Ashfield lateral",
        operator="Northmoor Gas",
        commodity=Commodity.NATURAL_GAS,
        length_m=18_500.0,
        nominal_diameter_mm=323.9,
        installed_year=1974,
    )


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
