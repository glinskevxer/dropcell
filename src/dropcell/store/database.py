"""The connection, and the handful of rules every caller has to get right.

SQLite will happily run without foreign keys enforced, with a journal mode that
loses the last transaction on a hard power cut, and with a busy timeout of zero
so a second process fails instantly instead of waiting. None of those defaults
suit a register that a field crew syncs into from a laptop in a van, so the
connection is opened once, here, with all of them set.

Durability is set to NORMAL rather than FULL, and only because the journal is
in write ahead log mode. In that pairing a transaction survives the process
being killed and every kind of crash short of the machine losing power, and the
worst a power cut can do is lose the last few commits rather than corrupt
anything. FULL fsyncs on every commit, which on an import of forty thousand
readings is the whole of the runtime, and it buys protection against a laptop
losing power in the seconds after somebody typed a command.

Errors are translated on the way out. A caller trying to insert a second test
point with the same code should catch ``ConflictError`` and print something
useful, not catch ``sqlite3.IntegrityError`` and have to read the message text
to work out which constraint fired.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any

from dropcell.errors import ConflictError, StoreError

BUSY_TIMEOUT_MS = 5000
CACHE_KB = 16_000
SYNCHRONOUS = "NORMAL"


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the register with the pragmas this package assumes are set."""
    target = str(path)
    try:
        connection = sqlite3.connect(target, isolation_level=None)
    except sqlite3.Error as exc:
        raise StoreError("cannot open the register", path=target) from exc
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    if target == ":memory:":
        return connection
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA synchronous = {SYNCHRONOUS};")
    connection.execute(f"PRAGMA cache_size = -{CACHE_KB}")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block inside one immediate transaction, rolling back on anything raised.

    ``BEGIN IMMEDIATE`` takes the write lock up front. Deferred transactions take
    it on the first write, which means two processes can both start reading,
    both decide to write, and one of them gets a busy error partway through work
    it thought it had already committed to.
    """
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")


class Database:
    """A thin wrapper that keeps the error translation in one place."""

    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self._connection = connect(path)
        self.statements = 0

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying connection, for the few places that need it raw."""
        return self._connection

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Run one statement and hand back its cursor.

        The counter is not instrumentation for its own sake. Several of the
        reports walk a few hundred posts, and the difference between one query
        and one query per post is the difference between a report that runs and
        one nobody waits for. A count is the only way to hold that in a test.
        """
        self.statements += 1
        try:
            return self._connection.execute(sql, tuple(parameters))
        except sqlite3.IntegrityError as exc:
            raise ConflictError("the register refused that write", reason=str(exc)) from exc
        except sqlite3.Error as exc:
            raise StoreError("statement failed", reason=str(exc)) from exc

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> sqlite3.Cursor:
        """Run one statement over many parameter sets."""
        self.statements += 1
        try:
            return self._connection.executemany(sql, [tuple(row) for row in rows])
        except sqlite3.IntegrityError as exc:
            raise ConflictError("the register refused that write", reason=str(exc)) from exc
        except sqlite3.Error as exc:
            raise StoreError("statement failed", reason=str(exc)) from exc

    def query(self, sql: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Run a select and read every row."""
        return self.execute(sql, parameters).fetchall()

    def query_one(self, sql: str, parameters: Sequence[Any] = ()) -> sqlite3.Row | None:
        """Run a select that is expected to match at most one row."""
        rows = self.execute(sql, parameters).fetchmany(2)
        if len(rows) > 1:
            raise StoreError("expected at most one row", sql=sql)
        return rows[0] if rows else None

    def scalar(self, sql: str, parameters: Sequence[Any] = ()) -> Any:
        """Read a single value out of a single row."""
        row = self.query_one(sql, parameters)
        return None if row is None else row[0]

    @contextmanager
    def transaction(self) -> Iterator[Database]:
        """Run a block inside one immediate transaction."""
        with transaction(self._connection):
            yield self

    def close(self) -> None:
        """Close the connection. Safe to call twice."""
        try:
            self._connection.close()
        except sqlite3.Error as exc:
            raise StoreError("cannot close the register", path=self.path) from exc

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
