"""Commands for getting files into the register.

Each command prints what landed, what was set aside and why. That output is the
whole point: an import that says nothing is an import nobody checks, and the
rows that did not land are exactly the ones somebody has to go and chase.

There is a dry run on every one of them. Field data arrives from people who are
not in the office and cannot be asked a question quickly, so being able to see
what a file would do before it does it saves a day.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.cli.outcome import report_dry_run, report_outcome
from dropcell.electrodes import Electrode
from dropcell.ingest.annual import ImportOutcome, import_annual
from dropcell.ingest.profiles import get_profile, profile_names
from dropcell.ingest.reader import read_text
from dropcell.ingest.rectifier import import_rectifier_checks
from dropcell.ingest.validate import identify, try_profile
from dropcell.report.table import Column, Table
from dropcell.stationing import Convention
from dropcell.store.imports import ImportLedger

RUN_COLUMNS = (
    Column("id", "Run", align="right"),
    Column("when", "Loaded"),
    Column("kind", "Kind"),
    Column("profile", "Profile"),
    Column("source", "File", width=30),
    Column("in", "Rows in", align="right"),
    Column("out", "Held", align="right"),
)


@click.group("import")
def import_group() -> None:
    """Load vendor files into the register."""


def _report(outcome: ImportOutcome) -> None:
    report_outcome(
        outcome.run,
        landed=outcome.written,
        noun="rows",
        quarantined=outcome.quarantined,
        reasons=outcome.reasons(),
    )


def _dry_run(text: str, profile_name: str, convention: Convention, source: str) -> None:
    result = read_text(text, get_profile(profile_name), convention=convention, source=source)
    report_dry_run(
        result.accepted, result.rejected, [held.summary for held in result.quarantine]
    )


@import_group.command("profiles")
@pass_context
@handled
def list_profiles(context: Context) -> None:
    """List the file formats this build knows."""
    table = Table(columns=(Column("name", "Profile"), Column("about", "Reads", width=52)))
    for name in profile_names():
        table.add(name=name, about=get_profile(name).description)
    for profile in context.settings.profiles:
        table.add(name=profile.name, about=profile.description)
    click.echo(table.render())


@import_group.command("annual")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--electrode",
    type=click.Choice([str(item) for item in Electrode]),
    default=str(Electrode.CSE),
    show_default=True,
)
@click.option("--dry-run", is_flag=True, help="Say what would happen and stop.")
@pass_context
@handled
def import_annual_command(context: Context, path: Path, electrode: str, dry_run: bool) -> None:
    """Load an annual test post survey."""
    text = path.read_text(encoding="utf-8")
    if dry_run:
        _dry_run(text, "annual", Convention.FOOT, path.name)
        return
    outcome = import_annual(
        context.database(),
        text,
        now=dt.datetime.combine(context.today, dt.time(12, 0)),
        source=path.name,
        electrode=Electrode(electrode),
    )
    _report(outcome)


@import_group.command("rectifier")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Say what would happen and stop.")
@pass_context
@handled
def import_rectifier_command(context: Context, path: Path, dry_run: bool) -> None:
    """Load a rectifier check sheet."""
    text = path.read_text(encoding="utf-8")
    if dry_run:
        _dry_run(text, "rectifier", Convention.FOOT, path.name)
        return
    outcome = import_rectifier_checks(
        context.database(),
        text,
        now=dt.datetime.combine(context.today, dt.time(12, 0)),
        source=path.name,
    )
    _report(outcome)


@import_group.command("runs")
@click.option("--limit", type=int, default=20, show_default=True)
@click.option("--kind", default=None, help="Only runs of this kind.")
@pass_context
@handled
def list_runs(context: Context, limit: int, kind: str | None) -> None:
    """List what has been loaded."""
    ledger = ImportLedger(context.database())
    table = Table(columns=RUN_COLUMNS, empty_note="nothing has been loaded")
    for run in ledger.recent(limit, kind=kind):
        table.add(
            id=run.run_id,
            when=run.imported_at.date().isoformat(),
            kind=run.kind,
            profile=run.profile,
            source=run.source,
            **{"in": run.accepted, "out": run.rejected},
        )
    click.echo(table.render())


@import_group.command("held")
@click.argument("run_id", type=int)
@pass_context
@handled
def show_held(context: Context, run_id: int) -> None:
    """Show the rows one run could not read."""
    ledger = ImportLedger(context.database())
    run = ledger.get(run_id)
    held = ledger.quarantine_for(run_id)
    click.echo(f"run {run.run_id}, {run.source or 'unnamed'}, {len(held)} rows held")
    for row in held:
        click.echo(f"  {row.summary}")
        click.echo(f"    {', '.join(row.raw)}")


MATCH_COLUMNS = (
    Column("profile", "Profile"),
    Column("reads", "Reads"),
    Column("rows", "Rows in", align="right"),
    Column("held", "Held", align="right"),
    Column("missing", "Missing columns", width=34),
    Column("spare", "Headers it did not use", width=34),
)


@import_group.command("check")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--profile", "profile_name", default=None, help="Check against one profile.")
@pass_context
@handled
def check_file(context: Context, path: Path, profile_name: str | None) -> None:
    """Say what would happen to a file, without opening the register."""
    text = path.read_text(encoding="utf-8")
    if profile_name is not None:
        chosen = context.settings.profile(profile_name) or get_profile(profile_name)
        matches = [try_profile(text, chosen)]
    else:
        matches = identify(text)
        matches.extend(try_profile(text, profile) for profile in context.settings.profiles)
        matches.sort(key=lambda item: item.score, reverse=True)
    table = Table(columns=MATCH_COLUMNS, title=f"{path.name}")
    for match in matches:
        table.add(
            profile=match.profile,
            reads="yes" if match.readable else "no",
            rows=match.accepted if match.readable else None,
            held=match.rejected if match.readable else None,
            missing=", ".join(match.missing),
            spare=", ".join(match.unmatched_headers),
        )
    click.echo(table.render())
    readable = [match for match in matches if match.readable]
    if not readable:
        click.echo("")
        click.echo("no profile this build ships can read that file")
        return
    best = readable[0]
    click.echo("")
    click.echo(f"best match is {best.profile}, {best.accepted} rows would read")
    for header, field_name in best.matched:
        click.echo(f"  {header} -> {field_name}")
    for header in best.unmatched_headers:
        click.echo(f"  {header} -> nothing, this column would be ignored")
