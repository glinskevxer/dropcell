"""Commands for coupons.

The status command is the reason the rest of this exists. It puts the IR free
potential, the DC density and the AC density on one row, which is the only view
in the whole tool where the potential criteria and the AC limits are applied to
the same measurement, and the column that matters is the last one: whether a
report that printed only the potential would have called this spot healthy.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from dropcell.analysis.coupon import CouponAssessment, assess_coupon, worst_first
from dropcell.cli.context import Context, handled, pass_context
from dropcell.cli.outcome import report_outcome
from dropcell.ingest.coupon import import_coupon_readings
from dropcell.model.coupon import Coupon, CouponOrientation, CouponReading
from dropcell.report.table import Column, Table
from dropcell.store.coupons import CouponReadingRepository, CouponRepository
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.testpoints import TestPointRepository
from dropcell.units import parse_area_m2, parse_potential_mv

COUPON_COLUMNS = (
    Column("code", "Coupon"),
    Column("post", "Post"),
    Column("area", "Area cm2", align="right", format=".2f"),
    Column("facing", "Facing"),
    Column("read", "Last read"),
    Column("off", "IR free mV", align="right", format=".0f"),
    Column("dc", "DC A/m2", align="right", format=".2f"),
    Column("ac", "AC A/m2", align="right", format=".1f"),
    Column("hidden", "Potential hides it"),
)


@click.group("coupon")
def coupon_group() -> None:
    """Add coupons, record readings and see what they say."""


@coupon_group.command("add")
@click.argument("code")
@click.option("--post", "test_point_code", required=True)
@click.option("--area", default="1 cm2", show_default=True)
@click.option("--shunt", type=float, required=True, help="Shunt resistance in ohms.")
@click.option(
    "--facing",
    type=click.Choice([str(item) for item in CouponOrientation]),
    default=str(CouponOrientation.SIDE),
    show_default=True,
)
@click.option("--depth", type=float, default=1.2, show_default=True)
@click.option("--installed", required=True)
@pass_context
@handled
def add_coupon(
    context: Context,
    code: str,
    test_point_code: str,
    area: str,
    shunt: float,
    facing: str,
    depth: float,
    installed: str,
) -> None:
    """Add a coupon to a test post."""
    database = context.database()
    post = TestPointRepository(database).get(test_point_code)
    coupon = Coupon(
        code=code,
        test_point_code=post.code,
        area_m2=parse_area_m2(area),
        shunt_ohm=shunt,
        installed_on=dt.date.fromisoformat(installed),
        orientation=CouponOrientation(facing),
        depth_m=depth,
    )
    CouponRepository(database).add(coupon)
    click.echo(f"{coupon.code} added on {post.code}, {coupon.area_cm2:.2f} cm2")
    if not coupon.orientation.represents_worst_case:
        click.echo("  this one is not on the bottom, so it is not the pessimistic case")


@coupon_group.command("read")
@click.argument("code")
@click.option("--on", "on_mv", required=True)
@click.option("--disconnected", "disconnected_mv", default=None)
@click.option("--dc-shunt", "dc_shunt_mv", default=None)
@click.option("--ac-shunt", "ac_shunt_mv", default=None)
@click.option("--ac-volts", "ac_voltage_v", type=float, default=None)
@click.option("--date", "taken_on", default=None)
@click.option("--by", "technician", default="")
@pass_context
@handled
def read_coupon(
    context: Context,
    code: str,
    on_mv: str,
    disconnected_mv: str | None,
    dc_shunt_mv: str | None,
    ac_shunt_mv: str | None,
    ac_voltage_v: float | None,
    taken_on: str | None,
    technician: str,
) -> None:
    """File one coupon reading."""
    database = context.database()
    coupon = CouponRepository(database).get(code)
    reading = CouponReading(
        coupon_code=coupon.code,
        taken_on=dt.date.fromisoformat(taken_on) if taken_on else context.today,
        on_mv=parse_potential_mv(on_mv),
        disconnected_mv=None
        if disconnected_mv is None
        else parse_potential_mv(disconnected_mv),
        dc_shunt_mv=None if dc_shunt_mv is None else parse_potential_mv(dc_shunt_mv),
        ac_shunt_mv=None if ac_shunt_mv is None else parse_potential_mv(ac_shunt_mv),
        ac_voltage_v=ac_voltage_v,
        technician=technician,
    )
    CouponReadingRepository(database).add(reading)
    click.echo(f"{coupon.code} read at {reading.taken_on.isoformat()}")


@coupon_group.command("import")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@pass_context
@handled
def import_coupons(context: Context, path: Path) -> None:
    """Load a coupon file."""
    loaded = import_coupon_readings(
        context.database(),
        path.read_text(encoding="utf-8"),
        now=dt.datetime.combine(context.today, dt.time(12, 0)),
        source=path.name,
    )
    report_outcome(
        loaded.run,
        landed=loaded.written,
        noun="readings",
        quarantined=loaded.quarantined,
        reasons=loaded.reasons(),
        notes=[f"{item} carries nothing but a connected potential" for item in loaded.thin],
    )


@coupon_group.command("status")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def coupon_status(context: Context, line_code: str) -> None:
    """Show what every coupon on a line is measuring."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    posts = {post.code: post for post in TestPointRepository(database).for_line(line.code)}
    coupons = CouponRepository(database).for_line(line.code)
    readings = CouponReadingRepository(database)
    unread: list[Coupon] = []
    assessments: list[tuple[Coupon, CouponAssessment]] = []
    for coupon in coupons:
        latest = readings.latest(coupon.code)
        post = posts.get(coupon.test_point_code)
        segment = None
        if post is not None:
            segment = next((item for item in segments if item.contains(post.station)), None)
        if latest is None or segment is None:
            unread.append(coupon)
            continue
        assessments.append((coupon, assess_coupon(coupon, latest, segment)))
    table = Table(columns=COUPON_COLUMNS, empty_note="no coupons on this line")
    for coupon in unread:
        table.add(
            code=coupon.code,
            post=coupon.test_point_code,
            area=coupon.area_cm2,
            facing=str(coupon.orientation),
            read="never or off segment",
        )
    for coupon, assessment in worst_first_pairs(assessments):
        table.add(
            code=coupon.code,
            post=coupon.test_point_code,
            area=coupon.area_cm2,
            facing=str(coupon.orientation),
            read=assessment.taken_on.isoformat(),
            off=assessment.reading.disconnected_mv,
            dc=assessment.dc_density_a_per_m2,
            ac=assessment.ac_density_a_per_m2,
            hidden="yes" if assessment.looks_fine_on_potential_alone else "",
        )
    click.echo(table.render())


def worst_first_pairs(
    pairs: list[tuple[Coupon, CouponAssessment]],
) -> list[tuple[Coupon, CouponAssessment]]:
    """Order coupon and assessment pairs by how much AC the coupon is taking."""
    ordered = worst_first([assessment for _, assessment in pairs])
    by_code = {coupon.code: coupon for coupon, _ in pairs}
    return [(by_code[item.code], item) for item in ordered]
