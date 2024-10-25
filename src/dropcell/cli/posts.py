"""Commands for test posts and the readings taken at them.

A post is added with the leads it carries, because the lead set is what decides
which readings the post can even hold, and a post added without them is a post
that will quietly refuse the first reading somebody tries to file against it.

Readings are entered one at a time here. Bulk entry is the import commands'
job, and this is for the reading somebody took on the way past a post that was
not on the round.
"""

from __future__ import annotations

import datetime as dt

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.electrodes import Electrode
from dropcell.model.enums import LeadKind
from dropcell.model.reading import Reading
from dropcell.model.testpoint import TestPoint
from dropcell.report.table import Column, Table
from dropcell.stationing import Station
from dropcell.store.lines import LineRepository
from dropcell.store.readings import ReadingRepository
from dropcell.store.testpoints import TestPointRepository
from dropcell.units import parse_potential_mv

POST_COLUMNS = (
    Column("code", "Post"),
    Column("station", "Station", align="right"),
    Column("leads", "Leads", width=30),
    Column("installed", "Installed"),
    Column("cell", "Fixed cell"),
    Column("last", "Last read"),
)

READING_COLUMNS = (
    Column("date", "Date"),
    Column("lead", "Lead"),
    Column("on", "On mV", align="right", format=".0f"),
    Column("off", "Off mV", align="right", format=".0f"),
    Column("native", "Native mV", align="right", format=".0f"),
    Column("ir", "IR mV", align="right", format=".0f"),
    Column("cell", "Cell"),
    Column("by", "By", width=16),
)


@click.group("post")
def post_group() -> None:
    """Add, list and read test posts."""


@post_group.command("add")
@click.argument("code")
@click.option("--line", "line_code", required=True)
@click.option("--at", "station", required=True, help="Station, in the line's convention.")
@click.option(
    "--lead",
    "leads",
    multiple=True,
    type=click.Choice([str(item) for item in LeadKind]),
    default=(str(LeadKind.PIPE),),
    show_default=True,
    help="Give once per lead the post carries.",
)
@click.option("--installed", required=True, help="Date the post went in, as YYYY-MM-DD.")
@click.option("--fixed-cell", is_flag=True, help="The post has a permanent reference cell.")
@click.option("--description", default="", help="Where to find it.")
@pass_context
@handled
def add_post(
    context: Context,
    code: str,
    line_code: str,
    station: str,
    leads: tuple[str, ...],
    installed: str,
    fixed_cell: bool,
    description: str,
) -> None:
    """Add a test post to a line."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    post = TestPoint(
        code=code,
        line_code=line.code,
        station=line.require_on_line(Station.parse(station, line.convention)),
        leads=frozenset(LeadKind(item) for item in leads),
        installed_on=dt.date.fromisoformat(installed),
        description=description,
        permanent_reference_cell=fixed_cell,
    )
    TestPointRepository(database).add(post)
    click.echo(f"{post.code} added at {line.format_station(post.station)}")


@post_group.command("list")
@click.option("--line", "line_code", required=True)
@click.option(
    "--lead",
    "lead",
    type=click.Choice([str(item) for item in LeadKind]),
    default=None,
    help="Only posts carrying this lead.",
)
@pass_context
@handled
def list_posts(context: Context, line_code: str, lead: str | None) -> None:
    """List the posts on one line."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    posts = TestPointRepository(database)
    readings = ReadingRepository(database)
    found = posts.with_lead(line.code, LeadKind(lead)) if lead else posts.for_line(line.code)
    table = Table(columns=POST_COLUMNS, empty_note="no posts on this line")
    for post in found:
        last = readings.last_read_on(post.code, LeadKind.PIPE)
        table.add(
            code=post.code,
            station=line.format_station(post.station),
            leads=", ".join(sorted(str(item) for item in post.leads)),
            installed=post.installed_on.isoformat(),
            cell="yes" if post.permanent_reference_cell else "",
            last=last.isoformat() if last else "never",
        )
    click.echo(table.render())


@post_group.command("show")
@click.argument("code")
@click.option("--limit", type=int, default=20, show_default=True)
@pass_context
@handled
def show_post(context: Context, code: str, limit: int) -> None:
    """Show one post and its recent readings."""
    database = context.database()
    post = TestPointRepository(database).get(code)
    line = LineRepository(database).get(post.line_code)
    history = ReadingRepository(database).for_point(post.code)
    click.echo(f"{post.code}  on {line.code} at {line.format_station(post.station)}")
    click.echo(f"leads       {', '.join(sorted(str(item) for item in post.leads))}")
    click.echo(f"installed   {post.installed_on.isoformat()}")
    if post.description:
        click.echo(f"where       {post.description}")
    click.echo("")
    table = Table(columns=READING_COLUMNS, empty_note="never read")
    for reading in history[-limit:]:
        table.add(
            date=reading.taken_on.isoformat(),
            lead=str(reading.lead),
            on=reading.on_cse_mv,
            off=reading.off_cse_mv,
            native=reading.native_mv,
            ir=reading.ir_drop_mv,
            cell=reading.cell_serial,
            by=reading.technician,
        )
    click.echo(table.render())


@post_group.command("read")
@click.argument("code")
@click.option("--on", "on_mv", required=True, help="On potential, such as -1.120 V.")
@click.option("--off", "off_mv", default=None, help="Instant off potential.")
@click.option("--native", "native_mv", default=None, help="Native potential.")
@click.option(
    "--lead",
    type=click.Choice([str(item) for item in LeadKind]),
    default=str(LeadKind.PIPE),
    show_default=True,
)
@click.option("--date", "taken_on", default=None, help="Defaults to the working date.")
@click.option(
    "--electrode",
    type=click.Choice([str(item) for item in Electrode]),
    default=str(Electrode.CSE),
    show_default=True,
)
@click.option("--cell", "cell_serial", default="", help="Serial of the half cell used.")
@click.option("--by", "technician", default="", help="Who took it.")
@click.option("--comment", default="")
@pass_context
@handled
def read_post(
    context: Context,
    code: str,
    on_mv: str,
    off_mv: str | None,
    native_mv: str | None,
    lead: str,
    taken_on: str | None,
    electrode: str,
    cell_serial: str,
    technician: str,
    comment: str,
) -> None:
    """File one reading against a post."""
    database = context.database()
    post = TestPointRepository(database).get(code)
    chosen = LeadKind(lead)
    post.require_lead(chosen)
    reading = Reading(
        test_point_code=post.code,
        lead=chosen,
        taken_on=dt.date.fromisoformat(taken_on) if taken_on else context.today,
        on_mv=parse_potential_mv(on_mv),
        off_mv=None if off_mv is None else parse_potential_mv(off_mv),
        native_mv=None if native_mv is None else parse_potential_mv(native_mv),
        electrode=Electrode(electrode),
        cell_serial=cell_serial,
        technician=technician,
        comment=comment,
    )
    ReadingRepository(database).add(reading)
    click.echo(f"{post.code} read at {reading.taken_on.isoformat()}")
