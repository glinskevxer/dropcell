"""Checking the register against itself.

Foreign keys stop a reading pointing at a post that does not exist. They do
nothing about a post sitting on pipe no segment describes, a line with no
segments at all, a coupon wired to a post that has no coupon lead, or two
readings whose IR drop runs the wrong way. Every one of those is a register that
loads, queries and reports without complaint and answers questions wrongly.

Each check returns rows rather than a verdict. Half of these are normal in a
register somebody is still building and all of them are normal in one being
migrated, so the decision about which of them matters belongs to the person
running it rather than to the exit code. The command that wraps this takes a
severity to fail on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository


class Severity(StrEnum):
    """How much a finding about the register itself matters."""

    NOTE = "note"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        """An order to sort and threshold by."""
        return {"note": 1, "warning": 2, "error": 3}[self.value]


@dataclass(frozen=True)
class HealthFinding:
    """One thing wrong with the register."""

    check: str
    severity: Severity
    subject: str
    detail: str

    def render(self) -> str:
        """One line for the report."""
        return f"{self.severity:<8} {self.check:<24} {self.subject:<14} {self.detail}"


def lines_without_segments(database: Database) -> list[HealthFinding]:
    """Lines nothing can be judged on, because no segment describes them."""
    segments = SegmentRepository(database)
    return [
        HealthFinding(
            check="line has no segments",
            severity=Severity.ERROR,
            subject=line.code,
            detail="no criterion can be chosen for anything on this line",
        )
        for line in LineRepository(database).all()
        if not segments.for_line(line.code)
    ]


def posts_off_segment(database: Database) -> list[HealthFinding]:
    """Posts standing on pipe no segment covers."""
    segments = SegmentRepository(database)
    posts = TestPointRepository(database)
    found: list[HealthFinding] = []
    for line in LineRepository(database).all():
        described = segments.for_line(line.code)
        if not described:
            continue
        for post in posts.for_line(line.code):
            if any(segment.contains(post.station) for segment in described):
                continue
            found.append(
                HealthFinding(
                    check="post off every segment",
                    severity=Severity.WARNING,
                    subject=post.code,
                    detail=f"at {line.format_station(post.station)} on {line.code}",
                )
            )
    return found


def segment_gaps(database: Database) -> list[HealthFinding]:
    """Stretches of a line that no segment describes."""
    segments = SegmentRepository(database)
    found: list[HealthFinding] = []
    for line in LineRepository(database).all():
        described = segments.for_line(line.code)
        if not described:
            continue
        cursor = 0.0
        for segment in described:
            if segment.extent.start.metres > cursor + 0.5:
                found.append(
                    HealthFinding(
                        check="gap in the segmentation",
                        severity=Severity.NOTE,
                        subject=line.code,
                        detail=(
                            f"{cursor:.0f} m to {segment.extent.start.metres:.0f} m"
                            " is not described"
                        ),
                    )
                )
            cursor = max(cursor, segment.extent.end.metres)
        if cursor < line.length_m - 0.5:
            found.append(
                HealthFinding(
                    check="gap in the segmentation",
                    severity=Severity.NOTE,
                    subject=line.code,
                    detail=f"{cursor:.0f} m to the end of the line is not described",
                )
            )
    return found


def coupons_without_a_lead(database: Database) -> list[HealthFinding]:
    """Coupons wired to a post whose lead set does not admit one."""
    rows = database.query(
        "SELECT c.code AS code, c.test_point_code AS post, t.leads AS leads"
        " FROM coupon c JOIN test_point t ON t.code = c.test_point_code"
        " ORDER BY c.code"
    )
    return [
        HealthFinding(
            check="coupon with no coupon lead",
            severity=Severity.WARNING,
            subject=str(row["code"]),
            detail=f"{row['post']} carries {row['leads']}",
        )
        for row in rows
        if "coupon" not in str(row["leads"]).split(",")
    ]


def reversed_ir_drops(database: Database) -> list[HealthFinding]:
    """Readings whose off potential is more negative than the on potential.

    The instant off is what is left when the soil drop is taken away, so it
    cannot be the more negative of the two on a structure taking current. When
    it is, the pair has been entered the wrong way round or the interrupter was
    out of step with the meter.
    """
    rows = database.query(
        "SELECT test_point_code, taken_on, on_mv, off_mv FROM reading"
        " WHERE off_mv IS NOT NULL AND off_mv < on_mv ORDER BY test_point_code, taken_on"
    )
    return [
        HealthFinding(
            check="off more negative than on",
            severity=Severity.WARNING,
            subject=str(row["test_point_code"]),
            detail=(
                f"{row['taken_on']} on {float(row['on_mv']):.0f} off {float(row['off_mv']):.0f}"
            ),
        )
        for row in rows
    ]


def rectifiers_never_checked(database: Database) -> list[HealthFinding]:
    """Units nobody has ever read."""
    rows = database.query(
        "SELECT r.tag AS tag, r.line_code AS line_code FROM rectifier r"
        " LEFT JOIN rectifier_check c ON c.rectifier_tag = r.tag"
        " WHERE c.id IS NULL ORDER BY r.tag"
    )
    return [
        HealthFinding(
            check="rectifier never checked",
            severity=Severity.WARNING,
            subject=str(row["tag"]),
            detail=f"on {row['line_code']}",
        )
        for row in rows
    ]


CHECKS = (
    lines_without_segments,
    posts_off_segment,
    segment_gaps,
    coupons_without_a_lead,
    reversed_ir_drops,
    rectifiers_never_checked,
)


def check_register(database: Database) -> list[HealthFinding]:
    """Run every check and sort what comes out worst first."""
    found: list[HealthFinding] = []
    for check in CHECKS:
        found.extend(check(database))
    return sorted(found, key=lambda item: (-item.severity.rank, item.check, item.subject))


def worst(findings: list[HealthFinding]) -> Severity | None:
    """The worst severity in a set of findings."""
    if not findings:
        return None
    return max((item.severity for item in findings), key=lambda item: item.rank)
