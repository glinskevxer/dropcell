from __future__ import annotations

import pytest

from dropcell.tools.check_migrations import main


def test_the_tool_passes_on_the_migration_list_as_it_stands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main() == 0
    assert "apply cleanly" in capsys.readouterr().out


def test_the_tool_fails_when_two_migrations_share_a_checksum(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from dropcell.store import migrations
    from dropcell.tools import check_migrations

    twin = migrations.Migration(1, "a", ("CREATE TABLE t (n INTEGER)",))
    other = migrations.Migration(2, "b", ("CREATE TABLE t (n INTEGER)",))
    monkeypatch.setattr(check_migrations, "MIGRATIONS", (twin, other))
    monkeypatch.setattr(migrations, "MIGRATIONS", (twin, other))
    assert main() == 1
    assert "same checksum" in capsys.readouterr().err


def test_the_tool_fails_on_a_gap_in_the_version_numbers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from dropcell.store import migrations
    from dropcell.tools import check_migrations

    gapped = (migrations.Migration(2, "b", ("CREATE TABLE t (n INTEGER)",)),)
    monkeypatch.setattr(check_migrations, "MIGRATIONS", gapped)
    monkeypatch.setattr(migrations, "MIGRATIONS", gapped)
    assert main() == 1
    assert "broken" in capsys.readouterr().err


def test_the_tool_fails_on_ddl_sqlite_will_not_take(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from dropcell.store import migrations
    from dropcell.tools import check_migrations

    broken = (migrations.Migration(1, "b", ("CREATE TABEL t (n INTEGER)",)),)
    monkeypatch.setattr(check_migrations, "MIGRATIONS", broken)
    monkeypatch.setattr(migrations, "MIGRATIONS", broken)
    assert main() == 1
    assert "failed to apply" in capsys.readouterr().err
