"""Commands for the free text notes.

There is no edit command. A note is what somebody saw on a day, and editing one
turns it into what somebody thinks they saw now. A note that was wrong gets
another note under it saying so, which is what the paper it replaced did.
"""

from __future__ import annotations

import datetime as dt

import click

from dropcell.cli.common import line_at
from dropcell.cli.context import Context, handled, pass_context
from dropcell.report.table import Column, Table
from dropcell.store.lines import LineRepository
from dropcell.store.observations import Observation, ObservationKind, ObservationRepository

NOTE_COLUMNS = (
    Column("id", "No", align="right"),
    Column("seen", "Seen"),
    Column("subject", "About", width=14),
    Column("kind", "Kind", width=12),
    Column("where", "Station", align="right"),
    Column("by", "By", width=14),
    Column("body", "Note", width=54),
)


@click.group("note")
def note_group() -> None:
    """Write down what no column will hold."""


@note_group.command("add")
@click.option("--line", "line_code", required=True)
@click.option("--about", "subject", required=True, help="What the note is about.")
@click.option(
    "--kind",
    type=click.Choice([str(item) for item in ObservationKind]),
    default=str(ObservationKind.GENERAL),
    show_default=True,
)
@click.option("--at", "station", default=None, help="Station, if the note has a place.")
@click.option("--date", "seen_on", default=None, help="Defaults to the working date.")
@click.option("--by", "seen_by", default="")
@click.argument("body", nargs=-1, required=True)
@pass_context
@handled
def add_note(
    context: Context,
    line_code: str,
    subject: str,
    kind: str,
    station: str | None,
    seen_on: str | None,
    seen_by: str,
    body: tuple[str, ...],
) -> None:
    """Write one note against a line."""
    database = context.database()
    if station is None:
        line = LineRepository(database).get(line_code)
        at = None
    else:
        line, at = line_at(database, line_code, station)
    note = Observation(
        line_code=line.code,
        subject=subject,
        kind=ObservationKind(kind),
        seen_on=dt.date.fromisoformat(seen_on) if seen_on else context.today,
        body=" ".join(body),
        seen_by=seen_by,
        station=at,
    )
    stored = ObservationRepository(database).add(note)
    click.echo(f"note {stored.observation_id} written against {stored.subject}")
    if stored.kind.blocks_work:
        click.echo("  this one is likely to stop somebody doing the job")


@note_group.command("list")
@click.option("--line", "line_code", required=True)
@click.option("--about", "subject", default=None, help="Only notes about one thing.")
@click.option(
    "--kind",
    type=click.Choice([str(item) for item in ObservationKind]),
    default=None,
)
@click.option("--since", default=None, help="Only notes from this date onwards.")
@click.option("--blocking", is_flag=True, help="Only the ones that stop work.")
@pass_context
@handled
def list_notes(
    context: Context,
    line_code: str,
    subject: str | None,
    kind: str | None,
    since: str | None,
    blocking: bool,
) -> None:
    """List the notes on a line."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    notes = ObservationRepository(database)
    if blocking:
        found = notes.blocking(line.code)
    else:
        found = notes.for_line(
            line.code,
            since=dt.date.fromisoformat(since) if since else None,
            kind=ObservationKind(kind) if kind else None,
        )
    if subject is not None:
        found = [item for item in found if item.subject == subject.strip()]
    table = Table(columns=NOTE_COLUMNS, empty_note="nothing written down")
    for item in found:
        table.add(
            id=item.observation_id,
            seen=item.seen_on.isoformat(),
            subject=item.subject,
            kind=str(item.kind),
            where="" if item.station is None else line.format_station(item.station),
            by=item.seen_by,
            body=item.body,
        )
    click.echo(table.render())


@note_group.command("remove")
@click.argument("number", type=int)
@click.confirmation_option(prompt="A note is a record of what somebody saw. Remove it?")
@pass_context
@handled
def remove_note(context: Context, number: int) -> None:
    """Remove a note that should never have been written."""
    ObservationRepository(context.database()).delete(number)
    click.echo(f"note {number} removed")
