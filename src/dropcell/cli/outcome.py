"""One shape for what an import command prints.

Five commands were each printing their own version of the same three things:
how much landed, how much could not be read, and one line per row that did not
make it. They had drifted into three different orders and two different words
for the same thing, and the one that mattered most was the one that had been
left out of two of them.

That is the count of rows held. A command that prints what it wrote and says
nothing about what it did not is a command that looks like a success on a file
that was half rejected, and every one of these is run by somebody who will not
look at the register again until next quarter.
"""

from __future__ import annotations

from collections.abc import Sequence

import click

from dropcell import logs
from dropcell.store.imports import ImportRun


def report_outcome(
    run: ImportRun,
    *,
    landed: int,
    noun: str,
    quarantined: int = 0,
    reasons: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> None:
    """Print what one import did, in the order every one of them prints it."""
    logs.imported(
        run.source,
        kind=run.kind,
        accepted=run.accepted,
        rejected=run.rejected,
        landed=landed,
        skipped=len(reasons),
    )
    click.echo(f"{landed} {noun} written from {run.source or 'the input'}")
    if quarantined:
        click.echo(f"{quarantined} rows could not be read")
    for reason in reasons:
        click.echo(f"  {reason}")
    for note in notes:
        click.echo(f"  {note}")


def report_dry_run(accepted: int, rejected: int, held: Sequence[str] = ()) -> None:
    """Print what one import would have done."""
    click.echo(f"{accepted} rows would read, {rejected} would be held")
    for line in held:
        click.echo(f"  {line}")
