"""The entry point.

Subcommands are grouped by the thing they act on rather than by what they do,
because that is how somebody looks for them. Everything about a line is under
``line``, everything about importing is under ``import``, and nothing sits at
the top level except the two commands that have nowhere else to go.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from dropcell import __version__, logs
from dropcell.cli.admin import register_group
from dropcell.cli.context import Context, handled, pass_context
from dropcell.cli.coupons import coupon_group
from dropcell.cli.findings import finding_group
from dropcell.cli.imports import import_group
from dropcell.cli.interference import plant_group
from dropcell.cli.lines import line_group, segment_group
from dropcell.cli.notes import note_group
from dropcell.cli.planning import plan_group
from dropcell.cli.posts import post_group
from dropcell.cli.rectifiers import rectifier_group
from dropcell.cli.reports import report_group
from dropcell.cli.survey import survey_group
from dropcell.cli.work import work_group
from dropcell.config import load_or_default
from dropcell.handbook import keys as handbook_keys
from dropcell.handbook import render as render_handbook
from dropcell.store.migrations import latest_version

DEFAULT_REGISTER = "cp.sqlite"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--register",
    "register_path",
    default=None,
    envvar="DROPCELL_REGISTER",
    help="Path to the SQLite register. Defaults to the settings file, then cp.sqlite.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    envvar="DROPCELL_CONFIG",
    help="Settings file. Defaults to the nearest dropcell.toml.",
)
@click.option(
    "--today",
    "today",
    default=None,
    help="Work to this date instead of the real one, as YYYY-MM-DD.",
)
@click.option("--quiet", "-q", is_flag=True, help="Say nothing but the output.")
@click.option(
    "--verbose",
    "-v",
    "verbosity",
    count=True,
    help="Log to standard error. Give twice for everything.",
)
@click.version_option(__version__, prog_name="dropcell")
@click.pass_context
def main(
    ctx: click.Context,
    register_path: str | None,
    config_path: Path | None,
    today: str | None,
    quiet: bool,
    verbosity: int,
) -> None:
    """Cathodic protection monitoring for buried steel pipelines."""
    logs.configure(verbosity, quiet=quiet)
    anchor = dt.date.fromisoformat(today) if today else dt.date.today()
    settings = load_or_default(config_path)
    ctx.obj = Context(
        register_path=register_path or settings.register or DEFAULT_REGISTER,
        today=anchor,
        quiet=quiet,
        settings=settings,
    )
    ctx.call_on_close(ctx.obj.close)


@main.command("init")
@pass_context
@handled
def init_command(context: Context) -> None:
    """Create the register, or bring an existing one up to date."""
    context.database()
    click.echo(f"{context.register_path} is at schema version {latest_version()}")


@main.command("handbook")
@click.argument("section", required=False, default=None)
@handled
def handbook_command(section: str | None) -> None:
    """Print the handbook, or one section of it.

    The sections are start, year, reading, groups, units and exits.
    """
    if section == "list":
        for key in handbook_keys():
            click.echo(key)
        return
    click.echo(render_handbook(section), nl=False)


@main.command("settings")
@pass_context
@handled
def settings_command(context: Context) -> None:
    """Print the settings in force and where they came from."""
    import dataclasses

    from dropcell.config import find

    found = find()
    click.echo(f"settings file  {found if found else 'none, using the defaults'}")
    click.echo(f"register       {context.register_path}")
    for field_name, value in dataclasses.asdict(context.settings).items():
        if field_name == "register":
            continue
        click.echo(f"{field_name:<22} {value if value != '' else '(not set)'}")


@main.command("schema")
@pass_context
@handled
def schema_command(context: Context) -> None:
    """List the migrations this build carries and which have been applied."""
    from dropcell.store.migrations import MIGRATIONS, applied

    done = applied(context.database())
    for migration in MIGRATIONS:
        mark = "applied" if migration.version in done else "pending"
        click.echo(f"{migration.version:>3}  {mark:<8}  {migration.name}")


main.add_command(line_group)
main.add_command(segment_group)
main.add_command(post_group)
main.add_command(import_group)
main.add_command(report_group)
main.add_command(plan_group)
main.add_command(finding_group)
main.add_command(rectifier_group)
main.add_command(survey_group)
main.add_command(plant_group)
main.add_command(work_group)
main.add_command(register_group)
main.add_command(coupon_group)
main.add_command(note_group)


if __name__ == "__main__":
    main()
