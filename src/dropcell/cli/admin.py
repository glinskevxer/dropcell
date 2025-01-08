"""Commands about the register itself rather than about the pipe.

They live in their own group because they are the ones somebody runs when
something is wrong, and having them mixed in with the reporting commands means
looking for them in a list of thirty at the moment they are needed.
"""

from __future__ import annotations

from pathlib import Path

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.report.table import Column, Table
from dropcell.store.health import Severity, check_register, worst
from dropcell.store.maintenance import (
    backup,
    foreign_key_violations,
    integrity,
    stats,
    vacuum,
)

STATS_COLUMNS = (
    Column("table", "Table", width=24),
    Column("rows", "Rows", align="right"),
)


@click.group("register")
def register_group() -> None:
    """Look after the register file itself."""


@register_group.command("check")
@click.option(
    "--fail-on",
    type=click.Choice([str(item) for item in Severity]),
    default=str(Severity.ERROR),
    show_default=True,
    help="Exit non zero when something at least this bad is found.",
)
@pass_context
@handled
def check_command(context: Context, fail_on: str) -> None:
    """Look for the problems foreign keys cannot catch."""
    database = context.database()
    damage = integrity(database)
    orphans = foreign_key_violations(database)
    for line in damage:
        click.echo(f"integrity  {line}")
    for line in orphans:
        click.echo(f"orphan     {line}")
    findings = check_register(database)
    for finding in findings:
        click.echo(finding.render())
    if not findings and not damage and not orphans:
        click.echo("nothing to report")
    threshold = Severity(fail_on)
    found = worst(findings)
    if damage or orphans:
        raise SystemExit(1)
    if found is not None and found.rank >= threshold.rank:
        raise SystemExit(1)


@register_group.command("stats")
@pass_context
@handled
def stats_command(context: Context) -> None:
    """Count what the register holds and how much room it takes."""
    figures = stats(context.database())
    table = Table(columns=STATS_COLUMNS, title="Rows")
    for name, count in sorted(figures.tables.items()):
        table.add(table=name, rows=count)
    click.echo(table.render())
    click.echo("")
    click.echo(f"{figures.rows} rows in {figures.size_bytes / 1024:.0f} kB")
    click.echo(
        f"{figures.free_bytes / 1024:.0f} kB free ({figures.free_share:.1%} of the file)"
    )
    if figures.worth_vacuuming:
        click.echo("enough free space that a vacuum would be worth running")


@register_group.command("backup")
@click.argument("destination", type=click.Path(dir_okay=False, path_type=Path))
@pass_context
@handled
def backup_command(context: Context, destination: Path) -> None:
    """Copy the register somewhere safe, consistently."""
    written = backup(context.database(), destination)
    click.echo(f"backed up to {written}")


@register_group.command("vacuum")
@pass_context
@handled
def vacuum_command(context: Context) -> None:
    """Rewrite the file to give back space that deletions left behind."""
    reclaimed = vacuum(context.database())
    click.echo(f"{reclaimed / 1024:.0f} kB reclaimed")
