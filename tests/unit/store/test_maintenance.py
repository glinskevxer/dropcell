from __future__ import annotations

from pathlib import Path

import pytest

from dropcell.errors import StoreError
from dropcell.model.line import Line
from dropcell.store.database import Database
from dropcell.store.lines import LineRepository
from dropcell.store.maintenance import (
    backup,
    foreign_key_violations,
    integrity,
    stats,
    table_names,
    vacuum,
)
from dropcell.store.migrations import migrate


def test_the_table_list_leaves_sqlite_own_tables_alone(database: Database) -> None:
    names = table_names(database)
    assert "line" in names
    assert not any(name.startswith("sqlite_") for name in names)


def test_stats_count_every_table(database: Database, line: Line) -> None:
    LineRepository(database).add(line)
    figures = stats(database)
    assert figures.tables["line"] == 1
    assert figures.tables["segment"] == 0
    assert figures.rows >= 1


def test_a_fresh_register_is_sound(database: Database) -> None:
    assert integrity(database) == []
    assert foreign_key_violations(database) == []


def test_a_small_register_is_not_worth_vacuuming(database: Database) -> None:
    assert not stats(database).worth_vacuuming


def test_the_free_share_of_an_untouched_register_is_nothing(
    database: Database,
) -> None:
    figures = stats(database)
    assert figures.free_share == pytest.approx(0.0)
    assert figures.size_bytes > 0


def test_a_backup_can_be_opened_and_carries_the_data(tmp_path: Path, line: Line) -> None:
    source = Database(str(tmp_path / "cp.sqlite"))
    migrate(source)
    LineRepository(source).add(line)
    target = backup(source, tmp_path / "copy.sqlite")
    copy = Database(str(target))
    assert LineRepository(copy).get("AL-2") == line


def test_a_backup_over_an_existing_file_replaces_it(tmp_path: Path, line: Line) -> None:
    source = Database(str(tmp_path / "cp.sqlite"))
    migrate(source)
    target = tmp_path / "copy.sqlite"
    target.write_text("not a database", encoding="utf-8")
    backup(source, target)
    assert Database(str(target)).scalar("SELECT count(*) FROM line") == 0


def test_a_backup_onto_a_directory_is_refused(tmp_path: Path) -> None:
    source = Database(":memory:")
    migrate(source)
    with pytest.raises(StoreError):
        backup(source, tmp_path)


def test_a_vacuum_never_makes_the_file_bigger(tmp_path: Path, line: Line) -> None:
    source = Database(str(tmp_path / "cp.sqlite"))
    migrate(source)
    LineRepository(source).add(line)
    LineRepository(source).delete("AL-2")
    assert vacuum(source) >= 0
