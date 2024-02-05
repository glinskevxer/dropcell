"""Shared fixtures.

Nothing here touches the network or the clock. Anything that needs a "now" is
handed one explicitly so a test never depends on the day it runs.
"""

from __future__ import annotations

import datetime as dt

import pytest


@pytest.fixture
def today() -> dt.date:
    """A fixed reference date used wherever a survey window needs an anchor."""
    return dt.date(2025, 3, 14)
