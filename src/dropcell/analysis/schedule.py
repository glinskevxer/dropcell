"""Building the monitoring register out of what the store holds.

The schedule code takes visit histories and knows nothing about tables. The
store holds readings and check sheets and knows nothing about rules. This is
the join, and it is worth having on its own because the mapping is not obvious
in one direction.

A test post's visits are the dates its pipe lead was read. Not the dates any
lead was read: a crew that reads the casing lead and skips the pipe lead has
not done the annual survey of that post, and counting it would let a whole
programme drift onto the wrong wire.

A post installed last month is not overdue. Its in service date is what the
interval runs from, and without that every new post on the line appears on the
overdue list the day it is added.
"""

from __future__ import annotations

from dropcell.model.enums import LeadKind
from dropcell.schedule.policy import AssetKind
from dropcell.schedule.register import AssetHistory
from dropcell.store.database import Database
from dropcell.store.readings import ReadingRepository
from dropcell.store.rectifiers import RectifierCheckRepository, RectifierRepository
from dropcell.store.testpoints import TestPointRepository


def post_histories(
    database: Database,
    line_code: str,
    *,
    lead: LeadKind = LeadKind.PIPE,
) -> list[AssetHistory]:
    """One history per test post on a line, from its readings."""
    posts = TestPointRepository(database).for_line(line_code)
    readings = ReadingRepository(database)
    histories: list[AssetHistory] = []
    for post in posts:
        if not post.has(lead):
            continue
        visits = tuple(reading.taken_on for reading in readings.for_point(post.code, lead=lead))
        histories.append(
            AssetHistory(
                code=post.code,
                kind=AssetKind.TEST_POINT,
                visits=visits,
                in_service_from=post.installed_on,
            )
        )
    return histories


def rectifier_histories(database: Database, line_code: str) -> list[AssetHistory]:
    """One history per rectifier on a line, from its check sheets."""
    units = RectifierRepository(database).for_line(line_code)
    checks = RectifierCheckRepository(database)
    return [
        AssetHistory(
            code=unit.tag,
            kind=AssetKind.RECTIFIER,
            visits=tuple(checks.visit_dates(unit.tag)),
            in_service_from=unit.installed_on,
        )
        for unit in units
    ]


def line_histories(
    database: Database,
    line_code: str,
    *,
    lead: LeadKind = LeadKind.PIPE,
) -> list[AssetHistory]:
    """Everything on one line that a monitoring rule applies to."""
    return [
        *post_histories(database, line_code, lead=lead),
        *rectifier_histories(database, line_code),
    ]
