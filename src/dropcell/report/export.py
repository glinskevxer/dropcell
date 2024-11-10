"""Writing the register out as CSV, because somebody always wants a spreadsheet.

The text tables are for reading. This is for the other half of the audience,
who will open it in a spreadsheet, add three columns of their own and mail it to
somebody. That means the output has to be boring: one header row, no title, no
totals, no blank lines, and every column in a form a spreadsheet will not
reinterpret.

Dates go out as ISO text and stay dates. Potentials go out as plain numbers with
no unit in the cell, because a cell holding ``-905 mV`` is text and will not
sum. The unit goes in the header where it belongs.

Nothing here rounds. A report rounds because a person is reading it; an export
does not, because the next thing that happens to these numbers is arithmetic.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Iterable, Sequence
from typing import Any

from dropcell.findings.finding import Finding
from dropcell.model.reading import Reading
from dropcell.stationing import Convention

FINDING_HEADERS = (
    "code",
    "line_code",
    "kind",
    "state",
    "raised_on",
    "due_by",
    "closed_on",
    "closed_by",
    "start_station",
    "end_station",
    "start_m",
    "end_m",
    "length_m",
    "summary",
    "source",
)

READING_HEADERS = (
    "test_point_code",
    "lead",
    "taken_on",
    "on_mv",
    "off_mv",
    "native_mv",
    "ir_drop_mv",
    "electrode",
    "cell_serial",
    "technician",
    "comment",
)


def write_rows(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """Render a header and its rows as CSV text."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return buffer.getvalue()


def _date(value: dt.date | None) -> str:
    return "" if value is None else value.isoformat()


def findings_csv(
    findings: Iterable[Finding],
    *,
    convention: Convention = Convention.FOOT,
) -> str:
    """Export the exception register."""
    rows = [
        (
            finding.code,
            finding.line_code,
            str(finding.kind),
            str(finding.state),
            _date(finding.raised_on),
            _date(finding.due_by),
            _date(finding.closed_on),
            finding.closed_by,
            finding.extent.start.format(convention),
            finding.extent.end.format(convention),
            finding.extent.start.metres,
            finding.extent.end.metres,
            finding.length_m,
            finding.summary,
            finding.source,
        )
        for finding in findings
    ]
    return write_rows(FINDING_HEADERS, rows)


def readings_csv(readings: Iterable[Reading]) -> str:
    """Export potentials, restated against copper sulfate."""
    rows = [
        (
            reading.test_point_code,
            str(reading.lead),
            _date(reading.taken_on),
            reading.on_cse_mv,
            reading.off_cse_mv,
            reading.native_mv,
            reading.ir_drop_mv,
            str(reading.electrode),
            reading.cell_serial,
            reading.technician,
            reading.comment,
        )
        for reading in readings
    ]
    return write_rows(READING_HEADERS, rows)
