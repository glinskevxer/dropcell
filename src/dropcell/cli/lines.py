"""Commands for lines and segments.

The two live together because nobody adds a line without adding segments to it,
and a line with no segments cannot be judged against anything.

Every option that takes a measurement takes it with its unit. ``--length
18500 m`` and ``--length 11.5 mi`` both work and land on the same number, which
matters because the person typing this has a drawing in front of them written
in whichever unit the drawing was made in.
"""

from __future__ import annotations

from pathlib import Path

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.model.enums import (
    ClassLocation,
    CoatingType,
    Commodity,
    LineStatus,
    ProtectionMethod,
)
from dropcell.model.line import Line
from dropcell.model.segment import Segment
from dropcell.report.table import Column, Table
from dropcell.stationing import Convention, Station, StationRange
from dropcell.store.lines import LineRepository
from dropcell.store.segments import SegmentRepository
from dropcell.store.transfer import export_line, import_line
from dropcell.units import parse_length_m

LINE_COLUMNS = (
    Column("code", "Code"),
    Column("name", "Name", width=28),
    Column("commodity", "Commodity", width=18),
    Column("length", "Length m", align="right", format=".0f"),
    Column("diameter", "OD mm", align="right", format=".1f"),
    Column("year", "Installed", align="right"),
    Column("convention", "Stationing"),
    Column("status", "Status", width=20),
    Column("retired", "Retired"),
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
@click.option("--in-service", is_flag=True, help="Leave the retired lines out.")
@pass_context
@handled
def list_lines(context: Context, in_service: bool) -> None:
    """List every line in the register."""
    lines = LineRepository(context.database())
    table = Table(columns=LINE_COLUMNS, empty_note="no lines in the register")
    for line in lines.in_service() if in_service else lines.all():
        table.add(
            code=line.code,
            name=line.name,
            commodity=str(line.commodity),
            length=line.length_m,
            diameter=line.nominal_diameter_mm,
            year=line.installed_year,
            convention=str(line.convention),
            status=str(line.status),
            retired=line.retired_on.isoformat() if line.retired_on else "",
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
    click.echo(f"status      {line.status}")
    if line.retired_on:
        click.echo(f"retired     {line.retired_on.isoformat()}")
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


@line_group.command("retire")
@click.argument("code")
@click.option(
    "--status",
    type=click.Choice([str(item) for item in LineStatus if item is not LineStatus.IN_SERVICE]),
    default=str(LineStatus.ABANDONED_IN_PLACE),
    show_default=True,
)
@click.option("--on", "retired_on", default=None, help="Defaults to the working date.")
@pass_context
@handled
def retire_line(context: Context, code: str, status: str, retired_on: str | None) -> None:
    """Take a line out of service without taking it out of the register.

    An abandoned line is still buried steel. It stops being monitored and it
    goes on interfering with everything around it, so it stays where it is with
    a status against it rather than being deleted.
    """
    import dataclasses
    import datetime as dt

    database = context.database()
    lines = LineRepository(database)
    line = lines.get(code)
    retired = lines.save(
        dataclasses.replace(
            line,
            status=LineStatus(status),
            retired_on=dt.date.fromisoformat(retired_on) if retired_on else context.today,
        )
    )
    click.echo(f"{retired.code} is {retired.status} from {retired.retired_on}")
    if retired.status.is_still_in_the_ground:
        click.echo("  the steel is still there, so it can still take and give interference")


@line_group.command("return")
@click.argument("code")
@pass_context
@handled
def return_line(context: Context, code: str) -> None:
    """Put a retired line back in service."""
    import dataclasses

    database = context.database()
    lines = LineRepository(database)
    line = lines.get(code)
    back = lines.save(dataclasses.replace(line, status=LineStatus.IN_SERVICE, retired_on=None))
    click.echo(f"{back.code} is back in service")


@line_group.command("export")
@click.argument("code")
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Write here instead of to standard output.",
)
@pass_context
@handled
def export_line_command(context: Context, code: str, out_path: str | None) -> None:
    """Write one line and everything on it out as a transfer document.

    Potentials go out against copper sulfate, whatever cell they were read
    with, because the receiving register has no way to know which cells the
    sending one had. That is a conversion rather than a loss, and it is the same
    conversion every report in here already does.
    """
    import json

    payload = export_line(context.database(), code)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if out_path is None:
        click.echo(text)
        return
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    counts = ", ".join(
        f"{len(payload[name])} {name.replace('_', ' ')}"
        for name in ("segments", "test_points", "readings", "findings")
    )
    context.say(f"{payload['line']['code']} written to {out_path}: {counts}")


@line_group.command("import")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@pass_context
@handled
def import_line_command(context: Context, path: Path) -> None:
    """Read a transfer document into this register."""
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        from dropcell.errors import ValidationError

        raise ValidationError(
            "that file is not readable JSON", path=str(path), reason=str(exc)
        ) from exc
    if not isinstance(payload, dict):
        from dropcell.errors import ValidationError

        raise ValidationError("a transfer document is one object", path=str(path))
    line = import_line(context.database(), payload)
    counts = ", ".join(
        f"{len(payload.get(name, []))} {name.replace('_', ' ')}"
        for name in ("segments", "test_points", "readings", "findings")
    )
    click.echo(f"{line.code} imported: {counts}")


@segment_group.command("split")
@click.argument("code")
@click.option("--at", "station", required=True, help="Where to put the boundary.")
@click.option("--left", "left_code", default=None, help="Code for the upstream half.")
@click.option("--right", "right_code", default=None, help="Code for the other half.")
@pass_context
@handled
def split_segment(
    context: Context,
    code: str,
    station: str,
    left_code: str | None,
    right_code: str | None,
) -> None:
    """Cut a segment in two, so a change can be recorded on one half.

    Both halves inherit everything from the original. Whatever actually changed
    is set on one of them afterwards, which keeps the split and the change as
    two separate statements about the line.
    """
    database = context.database()
    segments = SegmentRepository(database)
    original = segments.get(code)
    line = LineRepository(database).get(original.line_code)
    at = line.require_on_line(Station.parse(station, line.convention))
    left, right = segments.split(
        original.code, at, left_code=left_code or "", right_code=right_code or ""
    )
    click.echo(
        f"{original.code} split at {line.format_station(at)} into {left.code} and {right.code}"
    )
    click.echo(f"  {left.code}  {left.length_m:.0f} m")
    click.echo(f"  {right.code}  {right.length_m:.0f} m")
    click.echo("  both halves carry what the original did, so set the change on one")
