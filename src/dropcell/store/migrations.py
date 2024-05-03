"""Schema migrations, kept as data rather than as a directory of loose files.

Every migration is a version number, a name and the statements that move the
schema forward one step. They are applied in order, once, and the checksum of
what was applied is written down beside the version.

The checksum is the point. A migration that has already run somewhere is
frozen: editing its statements changes the database of anyone who has not run
it yet and changes nothing for anyone who has, and the two then disagree
forever with no error to say so. Recording the checksum turns that into a
refusal at startup instead of a mystery six months later.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

from dropcell.errors import MigrationError
from dropcell.store.database import Database

MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    checksum   TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Migration:
    """One step forward in the schema."""

    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        """A stable fingerprint of what this migration does."""
        body = "\n".join(" ".join(statement.split()) for statement in self.statements)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="lines and segments",
        statements=(
            """
            CREATE TABLE line (
                code                TEXT PRIMARY KEY,
                name                TEXT NOT NULL,
                operator            TEXT NOT NULL,
                commodity           TEXT NOT NULL,
                length_m            REAL NOT NULL CHECK (length_m > 0),
                nominal_diameter_mm REAL NOT NULL CHECK (nominal_diameter_mm > 0),
                installed_year      INTEGER NOT NULL,
                convention          TEXT NOT NULL,
                notes               TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE segment (
                code                   TEXT PRIMARY KEY,
                line_code              TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                start_m                REAL NOT NULL,
                end_m                  REAL NOT NULL,
                coating                TEXT NOT NULL,
                protection             TEXT NOT NULL,
                class_location         INTEGER NOT NULL CHECK (class_location BETWEEN 1 AND 4),
                outside_diameter_mm    REAL NOT NULL CHECK (outside_diameter_mm > 0),
                wall_thickness_mm      REAL NOT NULL CHECK (wall_thickness_mm > 0),
                installed_year         INTEGER NOT NULL,
                depth_of_cover_m       REAL NOT NULL CHECK (depth_of_cover_m > 0),
                soil_resistivity_ohm_m REAL,
                notes                  TEXT NOT NULL DEFAULT '',
                CHECK (end_m > start_m)
            )
            """,
            "CREATE INDEX segment_by_line ON segment (line_code, start_m)",
        ),
    ),
    Migration(
        version=2,
        name="test points and readings",
        statements=(
            """
            CREATE TABLE test_point (
                code                      TEXT PRIMARY KEY,
                line_code                 TEXT NOT NULL
                                          REFERENCES line(code) ON DELETE CASCADE,
                station_m                 REAL NOT NULL,
                leads                     TEXT NOT NULL,
                installed_on              TEXT NOT NULL,
                description               TEXT NOT NULL DEFAULT '',
                permanent_reference_cell  INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            CREATE TABLE reading (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                test_point_code  TEXT NOT NULL
                                 REFERENCES test_point(code) ON DELETE CASCADE,
                lead             TEXT NOT NULL,
                taken_on         TEXT NOT NULL,
                on_mv            REAL NOT NULL,
                off_mv           REAL,
                native_mv        REAL,
                electrode        TEXT NOT NULL DEFAULT 'cse',
                cell_serial      TEXT NOT NULL DEFAULT '',
                technician       TEXT NOT NULL DEFAULT '',
                comment          TEXT NOT NULL DEFAULT '',
                UNIQUE (test_point_code, lead, taken_on)
            )
            """,
            "CREATE INDEX test_point_by_line ON test_point (line_code, station_m)",
            "CREATE INDEX reading_by_date ON reading (taken_on)",
            "CREATE INDEX reading_by_point ON reading (test_point_code, taken_on)",
        ),
    ),
)


def latest_version() -> int:
    """The version a fully migrated register sits at."""
    return max(migration.version for migration in MIGRATIONS)


def check_sequence() -> None:
    """Refuse a migration list that is not one, two, three with no repeats."""
    versions = [migration.version for migration in MIGRATIONS]
    expected = list(range(1, len(MIGRATIONS) + 1))
    if versions != expected:
        raise MigrationError(
            "migration versions must run from one with no gaps",
            versions=versions,
            expected=expected,
        )


def applied(database: Database) -> dict[int, str]:
    """Version to checksum for everything already run against this register."""
    database.execute(MIGRATION_TABLE)
    rows = database.query("SELECT version, checksum FROM schema_migration ORDER BY version")
    return {int(row["version"]): str(row["checksum"]) for row in rows}


def verify(database: Database) -> None:
    """Refuse a register whose recorded migrations do not match this build."""
    check_sequence()
    known = {migration.version: migration for migration in MIGRATIONS}
    for version, checksum in applied(database).items():
        migration = known.get(version)
        if migration is None:
            raise MigrationError(
                "the register was migrated by a newer build of dropcell",
                version=version,
            )
        if migration.checksum != checksum:
            raise MigrationError(
                "a migration that already ran has been edited since",
                version=version,
                recorded=checksum,
                expected=migration.checksum,
            )


def migrate(database: Database, *, now: dt.datetime | None = None) -> list[Migration]:
    """Bring a register up to date and report which steps ran."""
    verify(database)
    stamp = (now or dt.datetime.now(dt.UTC)).isoformat(timespec="seconds")
    done = set(applied(database))
    ran: list[Migration] = []
    for migration in MIGRATIONS:
        if migration.version in done:
            continue
        with database.transaction():
            for statement in migration.statements:
                database.execute(statement)
            database.execute(
                "INSERT INTO schema_migration (version, name, checksum, applied_at)"
                " VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum, stamp),
            )
        ran.append(migration)
    return ran


def open_register(path: str) -> Database:
    """Open a register and make sure its schema is current."""
    database = Database(path)
    migrate(database)
    return database
