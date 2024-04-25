from __future__ import annotations

from pathlib import Path

import pytest

from dropcell.errors import ConflictError, StoreError
from dropcell.store.database import Database, connect, transaction


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    database.execute("CREATE TABLE post (code TEXT PRIMARY KEY, station REAL NOT NULL)")
    return database


def test_foreign_keys_are_on_from_the_start() -> None:
    connection = connect(":memory:")
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_a_file_backed_register_runs_in_write_ahead_log_mode(tmp_path: Path) -> None:
    connection = connect(tmp_path / "cp.sqlite")
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_rows_come_back_addressable_by_column_name(db: Database) -> None:
    db.execute("INSERT INTO post VALUES ('TP-114', 1245.5)")
    row = db.query_one("SELECT code, station FROM post")
    assert row is not None
    assert row["code"] == "TP-114"
    assert row["station"] == pytest.approx(1245.5)


def test_a_duplicate_key_comes_back_as_a_conflict(db: Database) -> None:
    db.execute("INSERT INTO post VALUES ('TP-114', 1245.5)")
    with pytest.raises(ConflictError):
        db.execute("INSERT INTO post VALUES ('TP-114', 900.0)")


def test_a_broken_statement_comes_back_as_a_store_error(db: Database) -> None:
    with pytest.raises(StoreError) as caught:
        db.execute("SELECT * FROM nothing_like_this")
    assert "reason" in caught.value.detail


def test_opening_a_register_in_a_directory_that_is_not_there_fails(tmp_path: Path) -> None:
    with pytest.raises(StoreError):
        Database(tmp_path / "missing" / "cp.sqlite")


def test_executemany_inserts_every_row(db: Database) -> None:
    db.executemany("INSERT INTO post VALUES (?, ?)", [("TP-1", 0.0), ("TP-2", 100.0)])
    assert db.scalar("SELECT count(*) FROM post") == 2


def test_executemany_reports_a_duplicate_as_a_conflict(db: Database) -> None:
    with pytest.raises(ConflictError):
        db.executemany("INSERT INTO post VALUES (?, ?)", [("TP-1", 0.0), ("TP-1", 1.0)])


def test_query_one_returns_nothing_when_nothing_matches(db: Database) -> None:
    assert db.query_one("SELECT * FROM post WHERE code = ?", ["TP-9"]) is None


def test_query_one_refuses_a_select_that_matched_twice(db: Database) -> None:
    db.executemany("INSERT INTO post VALUES (?, ?)", [("TP-1", 0.0), ("TP-2", 100.0)])
    with pytest.raises(StoreError):
        db.query_one("SELECT * FROM post")


def test_scalar_reads_one_value_or_nothing(db: Database) -> None:
    assert db.scalar("SELECT count(*) FROM post") == 0
    assert db.scalar("SELECT code FROM post WHERE code = 'TP-9'") is None


def test_a_transaction_that_raises_leaves_nothing_behind(db: Database) -> None:
    with pytest.raises(RuntimeError), db.transaction():
        db.execute("INSERT INTO post VALUES ('TP-1', 0.0)")
        raise RuntimeError("crew went home")
    assert db.scalar("SELECT count(*) FROM post") == 0


def test_a_transaction_that_finishes_keeps_its_writes(db: Database) -> None:
    with db.transaction():
        db.execute("INSERT INTO post VALUES ('TP-1', 0.0)")
    assert db.scalar("SELECT count(*) FROM post") == 1


def test_the_bare_transaction_helper_rolls_back_too() -> None:
    connection = connect(":memory:")
    connection.execute("CREATE TABLE t (n INTEGER)")
    with pytest.raises(ValueError), transaction(connection):
        connection.execute("INSERT INTO t VALUES (1)")
        raise ValueError("no")
    assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 0


def test_the_database_closes_itself_when_used_as_a_context_manager(tmp_path: Path) -> None:
    with Database(tmp_path / "cp.sqlite") as database:
        database.execute("CREATE TABLE t (n INTEGER)")
    with pytest.raises(StoreError):
        database.execute("SELECT 1")


def test_the_path_is_kept_for_error_messages(tmp_path: Path) -> None:
    target = tmp_path / "cp.sqlite"
    with Database(target) as database:
        assert database.path == str(target)
