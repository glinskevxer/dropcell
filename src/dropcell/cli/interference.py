"""Commands for the plant that exists to keep our current where it belongs.

Casings, crossings, bonds and isolating joints are added the same way and
tested the same way, so the commands look alike on purpose. What differs is the
reading each test takes and what a bad answer means, and that is in the verdict
line each command prints rather than in the shape of the command.

The tests print their verdict rather than storing it. A verdict is derived from
readings and thresholds, and storing it would freeze a judgement made under
whatever thresholds were current that afternoon.
"""

from __future__ import annotations

import datetime as dt

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.interference.bonds import Bond, BondCheck, BondKind, assess_bond
from dropcell.interference.casing import CasingTest, classify_casing
from dropcell.interference.foreign import Crossing, SwingTest, classify_swing
from dropcell.interference.isolation import (
    IsolationJoint,
    IsolationTest,
    JointKind,
    classify_isolation,
)
from dropcell.model.casing import Casing
from dropcell.report.table import Column, Table
from dropcell.stationing import Station
from dropcell.store.interference import (
    BondRepository,
    CasingRepository,
    CrossingRepository,
    IsolationJointRepository,
)
from dropcell.store.lines import LineRepository
from dropcell.units import parse_current_a, parse_length_m, parse_potential_mv

PLANT_COLUMNS = (
    Column("code", "Code"),
    Column("station", "Station", align="right"),
    Column("what", "What", width=40),
    Column("note", "Note", width=24),
)


@click.group("plant")
def plant_group() -> None:
    """Casings, crossings, bonds and isolating joints."""


@plant_group.command("add-casing")
@click.argument("code")
@click.option("--line", "line_code", required=True)
@click.option("--at", "station", required=True)
@click.option("--length", default="20 m", show_default=True)
@click.option("--carries", default="", help="What the crossing goes under.")
@click.option("--installed", required=True)
@pass_context
@handled
def add_casing(
    context: Context,
    code: str,
    line_code: str,
    station: str,
    length: str,
    carries: str,
    installed: str,
) -> None:
    """Add a cased crossing."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    casing = Casing(
        code=code,
        line_code=line.code,
        station=line.require_on_line(Station.parse(station, line.convention)),
        installed_on=dt.date.fromisoformat(installed),
        length_m=parse_length_m(length),
        carries=carries,
    )
    CasingRepository(database).add(casing)
    click.echo(f"{casing.code} added, {casing.length_m:.0f} m of casing")


@plant_group.command("add-crossing")
@click.argument("code")
@click.option("--line", "line_code", required=True)
@click.option("--at", "station", required=True)
@click.option("--operator", "foreign_operator", required=True)
@click.option("--structure", "foreign_structure", required=True)
@click.option("--bonded", is_flag=True)
@pass_context
@handled
def add_crossing(
    context: Context,
    code: str,
    line_code: str,
    station: str,
    foreign_operator: str,
    foreign_structure: str,
    bonded: bool,
) -> None:
    """Add a foreign structure crossing."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    crossing = Crossing(
        code=code,
        line_code=line.code,
        station=line.require_on_line(Station.parse(station, line.convention)),
        foreign_operator=foreign_operator,
        foreign_structure=foreign_structure,
        bonded=bonded,
    )
    CrossingRepository(database).add(crossing)
    click.echo(f"{crossing.code} added, crosses {crossing.foreign_operator}")


@plant_group.command("add-bond")
@click.argument("code")
@click.option("--line", "line_code", required=True)
@click.option("--at", "station", required=True)
@click.option("--kind", type=click.Choice([str(item) for item in BondKind]), required=True)
@click.option("--to", "to_structure", required=True)
@click.option("--design-current", required=True)
@click.option("--resistor", default=None, help="Resistor value in ohms.")
@click.option("--critical", is_flag=True, help="Protection depends on this bond.")
@click.option("--installed", required=True)
@pass_context
@handled
def add_bond(
    context: Context,
    code: str,
    line_code: str,
    station: str,
    kind: str,
    to_structure: str,
    design_current: str,
    resistor: str | None,
    critical: bool,
    installed: str,
) -> None:
    """Add a bond."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    bond = Bond(
        code=code,
        line_code=line.code,
        station=line.require_on_line(Station.parse(station, line.convention)),
        kind=BondKind(kind),
        to_structure=to_structure,
        installed_on=dt.date.fromisoformat(installed),
        design_current_a=parse_current_a(design_current),
        resistor_ohm=None if resistor is None else float(resistor),
        critical=critical,
    )
    BondRepository(database).add(bond)
    click.echo(f"{bond.code} added, read every {bond.check_interval_days} days")


@plant_group.command("add-joint")
@click.argument("code")
@click.option("--line", "line_code", required=True)
@click.option("--at", "station", required=True)
@click.option("--kind", type=click.Choice([str(item) for item in JointKind]), required=True)
@click.option("--separates", required=True)
@click.option("--surge-protector", is_flag=True)
@click.option("--installed", required=True)
@pass_context
@handled
def add_joint(
    context: Context,
    code: str,
    line_code: str,
    station: str,
    kind: str,
    separates: str,
    surge_protector: bool,
    installed: str,
) -> None:
    """Add an isolating joint."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    joint = IsolationJoint(
        code=code,
        line_code=line.code,
        station=line.require_on_line(Station.parse(station, line.convention)),
        kind=JointKind(kind),
        separates=separates,
        installed_on=dt.date.fromisoformat(installed),
        surge_protector_fitted=surge_protector,
    )
    IsolationJointRepository(database).add(joint)
    click.echo(f"{joint.code} added, separates {joint.separates}")


@plant_group.command("test-casing")
@click.argument("code")
@click.option("--pipe-on", required=True)
@click.option("--casing-on", required=True)
@click.option("--pipe-off", default=None)
@click.option("--casing-off", default=None)
@click.option("--date", "tested_on", default=None)
@pass_context
@handled
def test_casing(
    context: Context,
    code: str,
    pipe_on: str,
    casing_on: str,
    pipe_off: str | None,
    casing_off: str | None,
    tested_on: str | None,
) -> None:
    """Read a cased crossing and say whether it is shorted."""
    database = context.database()
    casing = CasingRepository(database).get(code)
    test = CasingTest(
        casing_code=casing.code,
        line_code=casing.line_code,
        station=casing.station,
        tested_on=dt.date.fromisoformat(tested_on) if tested_on else context.today,
        pipe_on_mv=parse_potential_mv(pipe_on),
        casing_on_mv=parse_potential_mv(casing_on),
        pipe_off_mv=None if pipe_off is None else parse_potential_mv(pipe_off),
        casing_off_mv=None if casing_off is None else parse_potential_mv(casing_off),
    )
    verdict = classify_casing(test)
    click.echo(f"{verdict.casing_code}: {verdict.status}")
    click.echo(f"  {verdict.separation_mv:.0f} mV between pipe and casing")
    click.echo(f"  {verdict.reason}")
    if verdict.due_by:
        click.echo(f"  deal with by {verdict.due_by.isoformat()}")


@plant_group.command("test-crossing")
@click.argument("code")
@click.option("--foreign-on", required=True, help="Foreign potential with our unit on.")
@click.option("--foreign-off", required=True, help="Foreign potential with our unit off.")
@click.option("--theirs-interrupted", is_flag=True, help="Their unit was interrupted too.")
@click.option("--date", "tested_on", default=None)
@pass_context
@handled
def test_crossing(
    context: Context,
    code: str,
    foreign_on: str,
    foreign_off: str,
    theirs_interrupted: bool,
    tested_on: str | None,
) -> None:
    """Read a swing test at a crossing and say whose current it is."""
    database = context.database()
    crossing = CrossingRepository(database).get(code)
    test = SwingTest(
        crossing_code=crossing.code,
        tested_on=dt.date.fromisoformat(tested_on) if tested_on else context.today,
        foreign_with_ours_on_mv=parse_potential_mv(foreign_on),
        foreign_with_ours_off_mv=parse_potential_mv(foreign_off),
        their_rectifier_interrupted=theirs_interrupted,
    )
    verdict = classify_swing(test)
    click.echo(f"{verdict.crossing_code}: {verdict.verdict}")
    click.echo(f"  {verdict.foreign_swing_mv:+.0f} mV swing on their structure")
    click.echo(f"  {verdict.reason}")
    if verdict.verdict.needs_mitigation:
        owner = "ours" if verdict.verdict.is_our_liability else "theirs"
        click.echo(f"  mitigation needed, liability {owner}")


@plant_group.command("test-bond")
@click.argument("code")
@click.option("--current", required=True)
@click.option("--reversed", "reversed_polarity", is_flag=True)
@click.option("--date", "checked_on", default=None)
@pass_context
@handled
def test_bond(
    context: Context,
    code: str,
    current: str,
    reversed_polarity: bool,
    checked_on: str | None,
) -> None:
    """Read a bond and say whether it is doing anything."""
    database = context.database()
    bond = BondRepository(database).get(code)
    check = BondCheck(
        bond_code=bond.code,
        checked_on=dt.date.fromisoformat(checked_on) if checked_on else context.today,
        current_a=parse_current_a(current),
        reversed_polarity=reversed_polarity,
    )
    health = assess_bond(bond, check)
    click.echo(f"{bond.code}: {health}")
    click.echo(f"  {check.current_a:.3f} A against a design of {bond.design_current_a:.3f} A")


@plant_group.command("test-joint")
@click.argument("code")
@click.option("--our-side", required=True)
@click.option("--other-side", required=True)
@click.option("--protector-lifted", is_flag=True, help="The surge protector was removed.")
@click.option("--date", "tested_on", default=None)
@pass_context
@handled
def test_joint(
    context: Context,
    code: str,
    our_side: str,
    other_side: str,
    protector_lifted: bool,
    tested_on: str | None,
) -> None:
    """Read an isolating joint and say whether it is still isolating."""
    database = context.database()
    joint = IsolationJointRepository(database).get(code)
    test = IsolationTest(
        joint_code=joint.code,
        tested_on=dt.date.fromisoformat(tested_on) if tested_on else context.today,
        our_side_mv=parse_potential_mv(our_side),
        other_side_mv=parse_potential_mv(other_side),
        surge_protector_removed=protector_lifted,
    )
    verdict = classify_isolation(test, joint)
    click.echo(f"{joint.code}: {verdict.status}")
    click.echo(f"  {verdict.separation_mv:.0f} mV between the two sides")
    click.echo(f"  {verdict.reason}")
    if verdict.due_by:
        click.echo(f"  deal with by {verdict.due_by.isoformat()}")


@plant_group.command("list")
@click.option("--line", "line_code", required=True)
@pass_context
@handled
def list_plant(context: Context, line_code: str) -> None:
    """List everything on a line that is not pipe, post or rectifier."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    table = Table(columns=PLANT_COLUMNS, empty_note="nothing else on this line")
    for casing in CasingRepository(database).for_line(line.code):
        table.add(
            code=casing.code,
            station=line.format_station(casing.station),
            what=f"casing under {casing.carries or 'something'}",
            note=f"{casing.length_m:.0f} m",
        )
    for crossing in CrossingRepository(database).for_line(line.code):
        table.add(
            code=crossing.code,
            station=line.format_station(crossing.station),
            what=f"crossing, {crossing.foreign_operator}",
            note="bonded" if crossing.bonded else "not bonded",
        )
    for bond in BondRepository(database).for_line(line.code):
        table.add(
            code=bond.code,
            station=line.format_station(bond.station),
            what=f"bond to {bond.to_structure}",
            note="critical" if bond.critical else str(bond.kind),
        )
    for joint in IsolationJointRepository(database).for_line(line.code):
        table.add(
            code=joint.code,
            station=line.format_station(joint.station),
            what=f"joint separating {joint.separates}",
            note=str(joint.kind),
        )
    click.echo(table.render())
