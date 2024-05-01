from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from dropcell.errors import MigrationError
from dropcell.store.database import Database
from dropcell.store.migrations import (
    MIGRATIONS,
    Migration,
    applied,
    check_sequence,
    latest_version,
    migrate,
    open_register,
    verify,
)


def test_the_migration_list_runs_from_one_with_no_gaps() -> None:
    check_sequence()
    assert [m.version for m in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))


def test_every_migration_has_a_name_and_at_least_one_statement() -> None:
    for migration in MIGRATIONS:
        assert migration.name.strip()
        assert migration.statements


def test_checksums_are_unique_across_the_list() -> None:
    checksums = [migration.checksum for migration in MIGRATIONS]
    assert len(set(checksums)) == len(checksums)


def test_a_checksum_ignores_whitespace_but_not_content() -> None:
    spaced = Migration(1, "x", ("CREATE   TABLE  t (n INTEGER)",))
    tight = Migration(1, "x", ("CREATE TABLE t (n INTEGER)",))
    other = Migration(1, "x", ("CREATE TABLE u (n INTEGER)",))
    assert spaced.checksum == tight.checksum
    assert spaced.checksum != other.checksum


def test_migrating_an_empty_register_runs_everything() -> None:
    database = Database(":memory:")
    ran = migrate(database)
    assert [m.version for m in ran] == [m.version for m in MIGRATIONS]
    assert set(applied(database)) == {m.version for m in MIGRATIONS}


def test_migrating_twice_runs_nothing_the_second_time() -> None:
    database = Database(":memory:")
    migrate(database)
    assert migrate(database) == []


def test_the_applied_stamp_is_the_time_it_was_handed() -> None:
    database = Database(":memory:")
    moment = dt.datetime(2025, 3, 14, 9, 30, tzinfo=dt.UTC)
    migrate(database, now=moment)
    row = database.query_one("SELECT applied_at FROM schema_migration WHERE version = 1")
    assert row is not None
    assert row["applied_at"].startswith("2025-03-14T09:30:00")


def test_a_register_from_a_newer_build_is_refused() -> None:
    database = Database(":memory:")
    migrate(database)
    database.execute(
        "INSERT INTO schema_migration VALUES (?, 'from the future', 'deadbeef', '2030-01-01')",
        (latest_version() + 1,),
    )
    with pytest.raises(MigrationError) as caught:
        verify(database)
    assert caught.value.detail["version"] == latest_version() + 1


def test_an_edited_migration_is_caught_by_its_checksum() -> None:
    database = Database(":memory:")
    migrate(database)
    database.execute("UPDATE schema_migration SET checksum = 'changed' WHERE version = 1")
    with pytest.raises(MigrationError) as caught:
        verify(database)
    assert caught.value.detail["recorded"] == "changed"
    assert caught.value.detail["expected"] == MIGRATIONS[0].checksum


def test_the_first_migration_builds_the_line_and_segment_tables() -> None:
    database = Database(":memory:")
    migrate(database)
    names = {
        row["name"]
        for row in database.query("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"line", "segment"} <= names


def test_a_segment_cannot_point_at_a_line_that_is_not_there() -> None:
    from dropcell.errors import ConflictError

    database = Database(":memory:")
    migrate(database)
    with pytest.raises(ConflictError):
        database.execute(
            "INSERT INTO segment (code, line_code, start_m, end_m, coating, protection,"
            " class_location, outside_diameter_mm, wall_thickness_mm, installed_year,"
            " depth_of_cover_m) VALUES ('S1', 'NOPE', 0, 100, 'coal_tar', 'impressed_current',"
            " 1, 323.9, 6.35, 1974, 1.2)"
        )


def test_a_segment_that_runs_backwards_is_refused_by_the_schema() -> None:
    from dropcell.errors import ConflictError

    database = Database(":memory:")
    migrate(database)
    database.execute(
        "INSERT INTO line VALUES ('AL-2', 'Ashfield', 'Northmoor', 'natural_gas',"
        " 18500, 323.9, 1974, 'foot', '')"
    )
    with pytest.raises(ConflictError):
        database.execute(
            "INSERT INTO segment (code, line_code, start_m, end_m, coating, protection,"
            " class_location, outside_diameter_mm, wall_thickness_mm, installed_year,"
            " depth_of_cover_m) VALUES ('S1', 'AL-2', 500, 100, 'coal_tar',"
            " 'impressed_current', 1, 323.9, 6.35, 1974, 1.2)"
        )


def test_open_register_migrates_a_file_on_the_way_through(tmp_path: Path) -> None:
    target = tmp_path / "cp.sqlite"
    with open_register(str(target)) as database:
        assert set(applied(database)) == {m.version for m in MIGRATIONS}
    with open_register(str(target)) as database:
        assert migrate(database) == []
