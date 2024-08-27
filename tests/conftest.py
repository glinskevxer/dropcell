"""Shared fixtures.

Nothing here touches the network or the clock. Anything that needs a "now" is
handed one explicitly so a test never depends on the day it runs.

The register fixtures live at the top rather than beside the store tests,
because the ingest and reporting suites need the same empty migrated register
and the same example line, and a second copy of them beside each suite drifts
the moment one of the records gains a field.
"""

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
def today() -> dt.date:
    """A fixed reference date used wherever a survey window needs an anchor."""
    return dt.date(2025, 3, 14)


@pytest.fixture
def database() -> Database:
    """An empty register with the current schema on it."""
    store = Database(":memory:")
    migrate(store, now=dt.datetime(2025, 3, 14, tzinfo=dt.UTC))
    return store


@pytest.fixture
def line() -> Line:
    """The example line every suite hangs its records off."""
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
    """A twelve hundred metre segment at the head of the example line."""
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
