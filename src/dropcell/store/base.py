"""The part of every repository that was the same in all of them.

Four repositories had written out their own find, get, all, count and delete,
and the five of them differed only in a table name, a column list and the word
used in the error. That is four places to fix a bug in and four places for the
normalisation of a lookup code to be quietly forgotten in one of them.

What is left in each repository is the part that is actually about that record:
the insert, the row to record mapping, and the queries that only make sense for
it. A repository that has nothing but the generic five is a repository that
should not exist.
"""

from __future__ import annotations

import sqlite3
from typing import ClassVar

from dropcell.errors import NotFoundError
from dropcell.model.ids import normalise_code
from dropcell.store.database import Database


class Repository[T]:
    """Lookup, listing and removal for one table keyed by a code."""

    table: ClassVar[str]
    columns: ClassVar[str]
    noun: ClassVar[str]
    key_column: ClassVar[str] = "code"
    order_by: ClassVar[str] = "code"

    def __init__(self, database: Database) -> None:
        self.database = database

    def to_record(self, row: sqlite3.Row) -> T:
        """Rebuild one record from a register row."""
        raise NotImplementedError

    @property
    def code_kind(self) -> str:
        """What a bad code is called in an error message."""
        return f"{self.noun} code"

    def normalise(self, code: str) -> str:
        """Fold a lookup code the same way the stored one was folded."""
        return normalise_code(code, kind=self.code_kind)

    def find(self, code: str) -> T | None:
        """The record under that code, or nothing."""
        row = self.database.query_one(
            f"SELECT {self.columns} FROM {self.table} WHERE {self.key_column} = ?",
            (self.normalise(code),),
        )
        return None if row is None else self.to_record(row)

    def get(self, code: str) -> T:
        """The record under that code, or a refusal naming it."""
        record = self.find(code)
        if record is None:
            raise NotFoundError(f"no {self.noun} with that code", code=self.normalise(code))
        return record

    def exists(self, code: str) -> bool:
        """Whether anything is stored under that code."""
        return self.find(code) is not None

    def all(self) -> list[T]:
        """Every record in the table, in its natural order."""
        rows = self.database.query(
            f"SELECT {self.columns} FROM {self.table} ORDER BY {self.order_by}"
        )
        return [self.to_record(row) for row in rows]

    def count(self) -> int:
        """How many records the table holds."""
        return int(self.database.scalar(f"SELECT count(*) FROM {self.table}") or 0)

    def delete(self, code: str) -> None:
        """Remove one record, refusing a code that is not there."""
        normalised = self.normalise(code)
        cursor = self.database.execute(
            f"DELETE FROM {self.table} WHERE {self.key_column} = ?", (normalised,)
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"no {self.noun} with that code", code=normalised)
