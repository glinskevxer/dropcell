"""The entry point.

Subcommands are grouped by the thing they act on rather than by what they do,
because that is how somebody looks for them. Everything about a line is under
``line``, everything about importing is under ``import``, and nothing sits at
the top level except the two commands that have nowhere else to go.
"""

from __future__ import annotations

import datetime as dt

import click

from dropcell import __version__
from dropcell.cli.context import Context, handled, pass_context
from dropcell.cli.imports import import_group
from dropcell.cli.lines import line_group, segment_group
from dropcell.cli.posts import post_group
from dropcell.store.migrations import latest_version

DEFAULT_REGISTER = "cp.sqlite"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--register",
    "register_path",
    default=DEFAULT_REGISTER,
    show_default=True,
    envvar="DROPCELL_REGISTER",
    help="Path to the SQLite register.",
)
@click.option(
    "--today",
    "today",
    default=None,
    help="Work to this date instead of the real one, as YYYY-MM-DD.",
)
@click.option("--quiet", "-q", is_flag=True, help="Say nothing but the output.")
@click.version_option(__version__, prog_name="dropcell")
@click.pass_context
def main(
    ctx: click.Context,
    register_path: str,
    today: str | None,
    quiet: bool,
) -> None:
    """Cathodic protection monitoring for buried steel pipelines."""
    anchor = dt.date.fromisoformat(today) if today else dt.date.today()
    ctx.obj = Context(register_path=register_path, today=anchor, quiet=quiet)
    ctx.call_on_close(ctx.obj.close)


@main.command("init")
@pass_context
@handled
def init_command(context: Context) -> None:
    """Create the register, or bring an existing one up to date."""
    context.database()
    click.echo(f"{context.register_path} is at schema version {latest_version()}")


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


if __name__ == "__main__":
    main()
