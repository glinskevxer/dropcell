"""Refuse a build whose migration list cannot produce a working register.

Run in CI. The list is data, so nothing in the normal test run forces every
statement through SQLite, and a typo in DDL that no test happens to exercise
would otherwise ship.
"""

from __future__ import annotations

import sys

from dropcell.errors import MigrationError
from dropcell.store.database import Database
from dropcell.store.migrations import MIGRATIONS, check_sequence, latest_version, migrate


def main() -> int:
    """Apply every migration to an empty in memory register and report."""
    try:
        check_sequence()
    except MigrationError as exc:
        print(f"migration list is broken: {exc}", file=sys.stderr)
        return 1
    checksums = {migration.checksum for migration in MIGRATIONS}
    if len(checksums) != len(MIGRATIONS):
        print("two migrations have the same checksum", file=sys.stderr)
        return 1
    database = Database(":memory:")
    try:
        ran = migrate(database)
    except Exception as exc:  # noqa: BLE001 - the point is to report anything at all
        print(f"migrations failed to apply: {exc}", file=sys.stderr)
        return 1
    if len(ran) != len(MIGRATIONS):
        print("a migration was skipped on an empty register", file=sys.stderr)
        return 1
    print(f"{len(ran)} migrations apply cleanly, schema is at version {latest_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
