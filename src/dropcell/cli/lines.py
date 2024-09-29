"""Commands for lines and segments.

The two live together because nobody adds a line without adding segments to it,
and a line with no segments cannot be judged against anything.

Every option that takes a measurement takes it with its unit. ``--length
18500 m`` and ``--length 11.5 mi`` both work and land on the same number, which
matters because the person typing this has a drawing in front of them written
in whichever unit the drawing was made in.
"""

from __future__ import annotations

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.model.enums import ClassLocation, CoatingType, Commodity, ProtectionMethod
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.report.table import Column, Table
from dropcell.stationing import Convention, Station, StationRange
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository
from dropcell.units import parse_length_m

LINE_COLUMNS = (
    Column("code", "Code"),
    Column("name", "Name", width=28),
    Column("commodity", "Commodity", width=18),
    Column("length", "Length m", align="right", format=".0f"),
    Column("diameter", "OD mm", align="right", format=".1f"),
    Column("year", "Installed", align="right"),
    Column("convention", "Stationing"),
)

SEGMENT_COLUMNS = (
    Column("code", "Code"),
    Column("from", "From", align="right"),
    Column("to", "To", align="right"),
    Column("length", "Length m", align="right", format=".0f"),
    Column("coating", "Coating", width=16),
    Column("protection", "Protection", width=18),
    Column("class", "Class", align="right"),
    Column("soil", "Soil ohm m", align="right", format=".1f"),
)


@click.group("line")
def line_group() -> None:
    """Add, list and inspect pipelines."""


@line_group.command("add")
@click.argument("code")
@click.option("--name", required=True, help="What the line is called.")
@click.option("--operator", required=True, help="Who runs it.")
@click.option(
    "--commodity",
    type=click.Choice([str(item) for item in Commodity]),
    default=str(Commodity.NATURAL_GAS),
    show_default=True,
)
@click.option("--length", required=True, help="Length with its unit, such as 18500 m.")
@click.option("--diameter", required=True, help="Outside diameter, such as 323.9 mm.")
@click.option("--installed", type=int, required=True, help="Year it went in the ground.")
@click.option(
    "--stationing",
    type=click.Choice([str(item) for item in Convention]),
    default=str(Convention.FOOT),
    show_default=True,
)
@click.option("--notes", default="", help="Anything worth writing down.")
@pass_context
@handled
def add_line(
    context: Context,
    code: str,
    name: str,
    operator: str,
    commodity: str,
    length: str,
    diameter: str,
    installed: int,
    stationing: str,
    notes: str,
) -> None:
    """Add a pipeline to the register."""
    line = Line(
        code=code,
        name=name,
        operator=operator,
        commodity=Commodity(commodity),
        length_m=parse_length_m(length),
        nominal_diameter_mm=parse_length_m(diameter) * 1000.0,
        installed_year=installed,
        convention=Convention(stationing),
        notes=notes,
    )
    LineRepository(context.database()).add(line)
    click.echo(f"{line.code} added, {line.length_m:.0f} m")


@line_group.command("list")
@pass_context
@handled
def list_lines(context: Context) -> None:
    """List every line in the register."""
    table = Table(columns=LINE_COLUMNS, empty_note="no lines in the register")
    for line in LineRepository(context.database()).all():
        table.add(
            code=line.code,
            name=line.name,
            commodity=str(line.commodity),
            length=line.length_m,
            diameter=line.nominal_diameter_mm,
            year=line.installed_year,
            convention=str(line.convention),
        )
    click.echo(table.render())


@line_group.command("show")
@click.argument("code")
@pass_context
@handled
def show_line(context: Context, code: str) -> None:
    """Show one line and the segments on it."""
    database = context.database()
    line = LineRepository(database).get(code)
    segments = SegmentRepository(database).for_line(line.code)
    click.echo(f"{line.code}  {line.name}")
    click.echo(f"operator    {line.operator}")
    click.echo(f"commodity   {line.commodity}")
    click.echo(f"length      {line.length_m:.0f} m")
    click.echo(f"diameter    {line.nominal_diameter_mm:.1f} mm")
    click.echo(f"installed   {line.installed_year}")
    click.echo(f"stationing  {line.convention}")
    if line.notes:
        click.echo(f"notes       {line.notes}")
    click.echo("")
    click.echo(_segment_table(line.convention, segments).render())


@line_group.command("remove")
@click.argument("code")
@click.confirmation_option(prompt="This removes the line and everything on it. Go on?")
@pass_context
@handled
def remove_line(context: Context, code: str) -> None:
    """Remove a line and everything hanging off it."""
    LineRepository(context.database()).delete(code)
    click.echo(f"{code} removed")


@click.group("segment")
def segment_group() -> None:
    """Add and list the segments of a line."""


@segment_group.command("add")
@click.argument("code")
@click.option("--line", "line_code", required=True, help="Which line it is on.")
@click.option("--from", "start", required=True, help="Start station.")
@click.option("--to", "end", required=True, help="End station.")
@click.option(
    "--coating",
    type=click.Choice([str(item) for item in CoatingType]),
    required=True,
)
@click.option(
    "--protection",
    type=click.Choice([str(item) for item in ProtectionMethod]),
    default=str(ProtectionMethod.IMPRESSED_CURRENT),
    show_default=True,
)
@click.option("--class-location", type=click.IntRange(1, 4), default=1, show_default=True)
@click.option("--diameter", required=True, help="Outside diameter, such as 323.9 mm.")
@click.option("--wall", required=True, help="Wall thickness, such as 6.35 mm.")
@click.option("--installed", type=int, required=True)
@click.option("--cover", default="1.2 m", show_default=True, help="Depth of cover.")
@click.option("--soil", default=None, help="Soil resistivity, such as 4500 ohm-cm.")
@click.option("--allow-overlap", is_flag=True, help="Let it sit on top of another segment.")
@pass_context
@handled
def add_segment(
    context: Context,
    code: str,
    line_code: str,
    start: str,
    end: str,
    coating: str,
    protection: str,
    class_location: int,
    diameter: str,
    wall: str,
    installed: int,
    cover: str,
    soil: str | None,
    allow_overlap: bool,
) -> None:
    """Add a segment to a line."""
    from dropcell.units import parse_resistivity_ohm_m

    database = context.database()
    line = LineRepository(database).get(line_code)
    segment = Segment(
        code=code,
        line_code=line.code,
        extent=StationRange(
            Station.parse(start, line.convention), Station.parse(end, line.convention)
        ),
        coating=CoatingType(coating),
        protection=ProtectionMethod(protection),
        class_location=ClassLocation(class_location),
        outside_diameter_mm=parse_length_m(diameter) * 1000.0,
        wall_thickness_mm=parse_length_m(wall) * 1000.0,
        installed_year=installed,
        depth_of_cover_m=parse_length_m(cover),
        soil_resistivity_ohm_m=None if soil is None else parse_resistivity_ohm_m(soil),
    )
    SegmentRepository(database).add(segment, allow_overlap=allow_overlap)
    click.echo(f"{segment.code} added, {segment.length_m:.0f} m")


@segment_group.command("list")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def list_segments(context: Context, line_code: str) -> None:
    """List the segments of one line."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    segments = SegmentRepository(database).for_line(line.code)
    click.echo(_segment_table(line.convention, segments).render())


def _segment_table(convention: Convention, segments: list[Segment]) -> Table:
    table = Table(columns=SEGMENT_COLUMNS, empty_note="no segments on this line")
    for segment in segments:
        table.add(
            code=segment.code,
            **{
                "from": segment.extent.start.format(convention),
                "to": segment.extent.end.format(convention),
                "class": int(segment.class_location),
            },
            length=segment.length_m,
            coating=str(segment.coating),
            protection=str(segment.protection),
            soil=segment.soil_resistivity_ohm_m,
        )
    return table
