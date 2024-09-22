"""What every command needs and how a failure reaches the terminal.

One object carries the register path, the date the command is working to, and
the connection once something has asked for it. Opening the register lazily
matters more than it looks: half these commands do not touch it at all, and a
command that fails on a missing file before it has printed its own help is
infuriating.

Errors are the other half. Every deliberate failure in this package is a
``DropcellError`` carrying a code and a detail mapping, and the whole of the
translation to a terminal happens here. A command that catches its own errors
and prints its own message is a command whose exit code will not match the
others.
"""

from __future__ import annotations

import datetime as dt
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, TypeVar

import click

from dropcell.errors import (
    ConflictError,
    DropcellError,
    IngestError,
    NotFoundError,
    PolicyError,
    ValidationError,
)
from dropcell.store.database import Database
from dropcell.store.migrations import migrate

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_CONFLICT = 4
EXIT_FAILURE = 1

EXIT_CODES: dict[type[DropcellError], int] = {
    ValidationError: EXIT_USAGE,
    PolicyError: EXIT_USAGE,
    IngestError: EXIT_USAGE,
    NotFoundError: EXIT_NOT_FOUND,
    ConflictError: EXIT_CONFLICT,
}


def exit_code_for(error: DropcellError) -> int:
    """The exit code one error should produce."""
    for kind in type(error).__mro__:
        if kind in EXIT_CODES:
            return EXIT_CODES[kind]
    return EXIT_FAILURE


@dataclass
class Context:
    """What a command is working with."""

    register_path: str
    today: dt.date
    quiet: bool = False
    _database: Database | None = field(default=None, repr=False)

    def database(self) -> Database:
        """Open the register, migrating it if it is behind."""
        if self._database is None:
            store = Database(self.register_path)
            migrate(store)
            self._database = store
        return self._database

    def close(self) -> None:
        """Close the register if it was ever opened."""
        if self._database is not None:
            self._database.close()
            self._database = None

    def say(self, message: str) -> None:
        """Print something that is not the command's output."""
        if not self.quiet:
            click.echo(message, err=True)


F = TypeVar("F", bound=Callable[..., Any])


def handled(function: F) -> F:
    """Turn a deliberate failure into a message and an exit code."""

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except DropcellError as error:
            click.echo(f"{error.code}: {error}", err=True)
            sys.exit(exit_code_for(error))

    return wrapper  # type: ignore[return-value]


pass_context = click.make_pass_decorator(Context)
