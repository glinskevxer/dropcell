"""Commands for rectifiers and the beds they feed.

The bed is added before the unit, because a rectifier with no groundbed is not
a thing that exists and the register will not hold one. That ordering annoys
people setting up a register for the first time and it is worth keeping: a bed
recorded as an afterthought is a bed with a guessed installation date and a
guessed anode count, and those two numbers are the entire life forecast.

The status command is the one that matters. It puts the unit's output beside
its nameplate and beside its bed's remaining life, because a unit at ninety
percent of rating on a bed with two years left is a capital job that needs to
be in next year's budget rather than a maintenance ticket.
"""

from __future__ import annotations

import datetime as dt

import click

from dropcell.analysis.groundbed import assess_bed
from dropcell.cli.context import Context, handled, pass_context
from dropcell.model.enums import AnodeMaterial, GroundbedKind
from dropcell.model.groundbed import Groundbed
from dropcell.model.rectifier import Rectifier, RectifierCheck
from dropcell.report.table import Column, Table
from dropcell.stationing import Station
from dropcell.store.lines import LineRepository
from dropcell.store.rectifiers import (
    GroundbedRepository,
    RectifierCheckRepository,
    RectifierRepository,
)
from dropcell.units import parse_current_a, parse_voltage_v

STATUS_COLUMNS = (
    Column("tag", "Unit"),
    Column("station", "Station", align="right"),
    Column("checked", "Checked"),
    Column("volts", "V", align="right", format=".1f"),
    Column("amps", "A", align="right", format=".2f"),
    Column("load", "Of rating", align="right", format=".0%"),
    Column("ohms", "Circuit ohm", align="right", format=".2f"),
    Column("bed", "Bed"),
    Column("spent", "Bed spent", align="right", format=".0%"),
    Column("life", "Years left", align="right", format=".1f"),
)


@click.group("rectifier")
def rectifier_group() -> None:
    """Add rectifiers, record checks and see where the beds have got to."""


@rectifier_group.command("add-bed")
@click.argument("code")
@click.option("--kind", type=click.Choice([str(item) for item in GroundbedKind]), required=True)
@click.option(
    "--material", type=click.Choice([str(item) for item in AnodeMaterial]), required=True
)
@click.option("--anodes", type=int, required=True, help="How many anodes went in.")
@click.option("--mass", required=True, help="Mass of one anode, such as 20 kg.")
@click.option("--installed", required=True, help="Date the bed went in.")
@click.option("--design-current", required=True, help="Current it was sized for.")
@click.option("--utilisation", type=float, default=0.85, show_default=True)
@pass_context
@handled
def add_bed(
    context: Context,
    code: str,
    kind: str,
    material: str,
    anodes: int,
    mass: str,
    installed: str,
    design_current: str,
    utilisation: float,
) -> None:
    """Add a groundbed."""
    bed = Groundbed(
        code=code,
        kind=GroundbedKind(kind),
        material=AnodeMaterial(material),
        anode_count=anodes,
        anode_mass_kg=_mass_kg(mass),
        installed_on=dt.date.fromisoformat(installed),
        design_current_a=parse_current_a(design_current),
        utilisation=utilisation,
    )
    GroundbedRepository(context.database()).add(bed)
    click.echo(
        f"{bed.code} added, {bed.installed_mass_kg:.0f} kg, "
        f"design life {bed.design_life_years():.0f} years"
    )


@rectifier_group.command("add")
@click.argument("tag")
@click.option("--line", "line_code", required=True)
@click.option("--at", "station", required=True)
@click.option("--bed", "groundbed_code", required=True)
@click.option("--rated-volts", required=True)
@click.option("--rated-amps", required=True)
@click.option("--coarse-taps", type=int, default=5, show_default=True)
@click.option("--fine-taps", type=int, default=4, show_default=True)
@click.option("--installed", required=True)
@click.option("--no-interrupter", is_flag=True, help="The unit has no interrupter fitted.")
@pass_context
@handled
def add_rectifier(
    context: Context,
    tag: str,
    line_code: str,
    station: str,
    groundbed_code: str,
    rated_volts: str,
    rated_amps: str,
    coarse_taps: int,
    fine_taps: int,
    installed: str,
    no_interrupter: bool,
) -> None:
    """Add a rectifier to a line."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    unit = Rectifier(
        tag=tag,
        line_code=line.code,
        station=line.require_on_line(Station.parse(station, line.convention)),
        groundbed_code=groundbed_code,
        rated_voltage_v=parse_voltage_v(rated_volts),
        rated_current_a=parse_current_a(rated_amps),
        coarse_taps=coarse_taps,
        fine_taps=fine_taps,
        installed_on=dt.date.fromisoformat(installed),
        interrupter_fitted=not no_interrupter,
    )
    RectifierRepository(database).add(unit)
    click.echo(f"{unit.tag} added at {line.format_station(unit.station)}")


@rectifier_group.command("check")
@click.argument("tag")
@click.option("--volts", required=True)
@click.option("--amps", required=True)
@click.option("--coarse", type=int, required=True)
@click.option("--fine", type=int, required=True)
@click.option("--hours", type=float, default=None)
@click.option("--date", "checked_on", default=None)
@click.option("--by", "technician", default="")
@click.option("--comment", default="")
@pass_context
@handled
def check_rectifier(
    context: Context,
    tag: str,
    volts: str,
    amps: str,
    coarse: int,
    fine: int,
    hours: float | None,
    checked_on: str | None,
    technician: str,
    comment: str,
) -> None:
    """Record one visit to a rectifier."""
    database = context.database()
    unit = RectifierRepository(database).get(tag)
    if not unit.is_valid_tap(coarse, fine):
        from dropcell.errors import ValidationError

        raise ValidationError(
            "that tap pair is not on this unit's board",
            tag=unit.tag,
            coarse=coarse,
            fine=fine,
            board=f"{unit.coarse_taps}x{unit.fine_taps}",
        )
    check = RectifierCheck(
        rectifier_tag=unit.tag,
        checked_on=dt.date.fromisoformat(checked_on) if checked_on else context.today,
        output_voltage_v=parse_voltage_v(volts),
        output_current_a=parse_current_a(amps),
        coarse_tap=coarse,
        fine_tap=fine,
        hour_meter=hours,
        technician=technician,
        comment=comment,
    )
    RectifierCheckRepository(database).add(check)
    click.echo(f"{unit.tag} checked at {check.checked_on.isoformat()}")


@rectifier_group.command("status")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def rectifier_status(context: Context, line_code: str) -> None:
    """Show every unit on a line beside its bed's remaining life."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    units = RectifierRepository(database).for_line(line.code)
    checks = RectifierCheckRepository(database)
    beds = GroundbedRepository(database)
    table = Table(columns=STATUS_COLUMNS, empty_note="no rectifiers on this line")
    for unit in units:
        latest = checks.latest(unit.tag)
        bed = beds.get(unit.groundbed_code)
        status = assess_bed(bed, checks.for_unit(unit.tag), as_of=context.today)
        table.add(
            tag=unit.tag,
            station=line.format_station(unit.station),
            checked=latest.checked_on.isoformat() if latest else "never",
            volts=latest.output_voltage_v if latest else None,
            amps=latest.output_current_a if latest else None,
            load=latest.load_fraction(unit) if latest else None,
            ohms=latest.circuit_resistance_ohm if latest else None,
            bed=bed.code,
            spent=status.spent_fraction,
            life=status.remaining_life_years,
        )
    click.echo(table.render())


def _mass_kg(text: str) -> float:
    from dropcell.errors import UnitError

    cleaned = text.strip().lower()
    for suffix, factor in (("kg", 1.0), ("g", 0.001), ("lb", 0.45359237)):
        if cleaned.endswith(suffix):
            try:
                return float(cleaned[: -len(suffix)].strip()) * factor
            except ValueError as exc:
                raise UnitError("cannot read a mass from this", text=text) from exc
    try:
        return float(cleaned)
    except ValueError as exc:
        raise UnitError("cannot read a mass from this", text=text) from exc
