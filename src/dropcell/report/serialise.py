"""Reports as JSON, for the things that read reports rather than the people.

The text reports are shaped for somebody reading them. Anything that consumes
them programmatically has to parse columns out of a table that is allowed to
change width, and that is a bad bargain for both sides: the report cannot be
improved without breaking a script, and the script breaks silently.

So the same objects come out as JSON with the same names the code uses. Two
rules make it worth relying on. Nothing is rounded, because the consumer is
going to do arithmetic. And a value that is not known is null rather than zero
or an empty string, so the difference between a post reading nothing and a post
nobody read survives the trip.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from dropcell.analysis.line import LineAssessment
from dropcell.findings.finding import Finding
from dropcell.report.ageing import AgeingRow
from dropcell.schedule.register import DueItem


def dump(payload: Any) -> str:
    """Render a payload the way every command that emits JSON should."""
    return json.dumps(payload, indent=2, sort_keys=True, default=_default)


def _default(value: Any) -> Any:
    if isinstance(value, dt.date | dt.datetime):
        return value.isoformat()
    raise TypeError(f"cannot serialise {type(value).__name__}")


def finding_payload(finding: Finding) -> dict[str, Any]:
    """One finding as JSON."""
    return {
        "code": finding.code,
        "line_code": finding.line_code,
        "kind": str(finding.kind),
        "state": str(finding.state),
        "raised_on": finding.raised_on,
        "due_by": finding.due_by,
        "closed_on": finding.closed_on,
        "closed_by": finding.closed_by or None,
        "start_m": finding.extent.start.metres,
        "end_m": finding.extent.end.metres,
        "length_m": finding.length_m,
        "summary": finding.summary,
        "source": finding.source or None,
    }


def protection_payload(assessment: LineAssessment) -> dict[str, Any]:
    """One line's protection assessment as JSON."""
    return {
        "line_code": assessment.line.code,
        "as_of": assessment.as_of,
        "posts": len(assessment.posts),
        "judged": len(assessment.assessed),
        "protected": len(assessment.protected),
        "under_criterion": len(assessment.under_criterion),
        "unread": len(assessment.unread),
        "stale": len(assessment.stale),
        "off_segment": len(assessment.off_segment),
        "protection_rate": assessment.protection_rate,
        "rows": [
            {
                "post": item.code,
                "station_m": item.post.station.metres,
                "segment": None if item.segment is None else item.segment.code,
                "criterion_set": item.criterion_set or None,
                "read_on": None if item.reading is None else item.reading.taken_on,
                "reading_age_days": item.reading_age_days,
                "on_mv": None if item.reading is None else item.reading.on_cse_mv,
                "off_mv": None if item.reading is None else item.reading.off_cse_mv,
                "protected": item.protected,
                "assessed": item.verdict is not None and item.verdict.assessed,
                "met": (
                    []
                    if item.verdict is None
                    else [entry.criterion for entry in item.verdict.met]
                ),
                "exceeded": (
                    []
                    if item.verdict is None
                    else [entry.criterion for entry in item.verdict.exceeded]
                ),
            }
            for item in assessment.posts
        ],
    }


def compliance_payload(register: list[DueItem], *, as_of: dt.date) -> dict[str, Any]:
    """A monitoring register as JSON."""
    return {
        "as_of": as_of,
        "pairs": len(register),
        "rows": [
            {
                "asset": item.asset_code,
                "asset_kind": str(item.asset_kind),
                "rule": item.rule_key,
                "next_due": item.next_due,
                "days_until_due": item.days_until_due,
                "overdue": item.overdue,
                "compliant": item.compliant,
                "ever_visited": item.ever_visited,
                "visits": list(item.result.visits),
                "reasons": list(item.result.reasons()),
            }
            for item in register
        ],
    }


def ageing_payload(rows: list[AgeingRow], *, as_of: dt.date) -> dict[str, Any]:
    """A finding ageing table as JSON."""
    return {
        "as_of": as_of,
        "rows": [
            {
                "kind": str(row.kind),
                "buckets": list(row.buckets),
                "total": row.total,
                "over_a_year": row.stale,
                "oldest_days": row.oldest_days,
            }
            for row in rows
        ],
    }
