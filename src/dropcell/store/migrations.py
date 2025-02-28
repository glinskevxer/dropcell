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
    Migration(
        version=3,
        name="findings",
        statements=(
            """
            CREATE TABLE finding (
                code          TEXT PRIMARY KEY,
                line_code     TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                kind          TEXT NOT NULL,
                raised_on     TEXT NOT NULL,
                start_m       REAL NOT NULL,
                end_m         REAL NOT NULL,
                summary       TEXT NOT NULL,
                state         TEXT NOT NULL DEFAULT 'open',
                due_by        TEXT,
                closed_on     TEXT,
                closed_by     TEXT NOT NULL DEFAULT '',
                closed_reason TEXT NOT NULL DEFAULT '',
                source        TEXT NOT NULL DEFAULT '',
                CHECK (end_m >= start_m)
            )
            """,
            """
            CREATE TABLE finding_event (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_code TEXT NOT NULL REFERENCES finding(code) ON DELETE CASCADE,
                happened_on  TEXT NOT NULL,
                from_state   TEXT NOT NULL,
                to_state     TEXT NOT NULL,
                actor        TEXT NOT NULL DEFAULT '',
                note         TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX finding_by_line ON finding (line_code, start_m)",
            "CREATE INDEX finding_by_state ON finding (state, due_by)",
            "CREATE INDEX finding_event_by_finding ON finding_event"
            " (finding_code, happened_on)",
        ),
    ),
    Migration(
        version=4,
        name="import ledger",
        statements=(
            """
            CREATE TABLE import_run (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT NOT NULL UNIQUE,
                profile      TEXT NOT NULL,
                kind         TEXT NOT NULL,
                source       TEXT NOT NULL DEFAULT '',
                imported_at  TEXT NOT NULL,
                accepted     INTEGER NOT NULL,
                rejected     INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE import_quarantine (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id     INTEGER NOT NULL REFERENCES import_run(id) ON DELETE CASCADE,
                row_number INTEGER NOT NULL,
                raw        TEXT NOT NULL,
                reasons    TEXT NOT NULL
            )
            """,
            "CREATE INDEX import_run_by_date ON import_run (imported_at)",
            "CREATE INDEX quarantine_by_run ON import_quarantine (run_id, row_number)",
        ),
    ),
    Migration(
        version=5,
        name="rectifiers and groundbeds",
        statements=(
            """
            CREATE TABLE groundbed (
                code            TEXT PRIMARY KEY,
                kind            TEXT NOT NULL,
                material        TEXT NOT NULL,
                anode_count     INTEGER NOT NULL CHECK (anode_count > 0),
                anode_mass_kg   REAL NOT NULL CHECK (anode_mass_kg > 0),
                installed_on    TEXT NOT NULL,
                design_current_a REAL NOT NULL CHECK (design_current_a > 0),
                utilisation     REAL NOT NULL CHECK (utilisation > 0 AND utilisation <= 1),
                description     TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE rectifier (
                tag                TEXT PRIMARY KEY,
                line_code          TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                station_m          REAL NOT NULL,
                groundbed_code     TEXT NOT NULL REFERENCES groundbed(code),
                rated_voltage_v    REAL NOT NULL CHECK (rated_voltage_v > 0),
                rated_current_a    REAL NOT NULL CHECK (rated_current_a > 0),
                coarse_taps        INTEGER NOT NULL CHECK (coarse_taps > 0),
                fine_taps          INTEGER NOT NULL CHECK (fine_taps > 0),
                installed_on       TEXT NOT NULL,
                interrupter_fitted INTEGER NOT NULL DEFAULT 1,
                description        TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE rectifier_check (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                rectifier_tag    TEXT NOT NULL REFERENCES rectifier(tag) ON DELETE CASCADE,
                checked_on       TEXT NOT NULL,
                output_voltage_v REAL NOT NULL CHECK (output_voltage_v >= 0),
                output_current_a REAL NOT NULL CHECK (output_current_a >= 0),
                coarse_tap       INTEGER NOT NULL,
                fine_tap         INTEGER NOT NULL,
                hour_meter       REAL,
                technician       TEXT NOT NULL DEFAULT '',
                comment          TEXT NOT NULL DEFAULT '',
                UNIQUE (rectifier_tag, checked_on)
            )
            """,
            "CREATE INDEX rectifier_by_line ON rectifier (line_code, station_m)",
            "CREATE INDEX rectifier_check_by_date ON rectifier_check"
            " (rectifier_tag, checked_on)",
        ),
    ),
    Migration(
        version=6,
        name="coupons",
        statements=(
            """
            CREATE TABLE coupon (
                code            TEXT PRIMARY KEY,
                test_point_code TEXT NOT NULL
                                REFERENCES test_point(code) ON DELETE CASCADE,
                area_m2         REAL NOT NULL CHECK (area_m2 > 0),
                shunt_ohm       REAL NOT NULL CHECK (shunt_ohm > 0),
                installed_on    TEXT NOT NULL,
                orientation     TEXT NOT NULL DEFAULT 'side',
                depth_m         REAL NOT NULL DEFAULT 1.2 CHECK (depth_m > 0),
                description     TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE coupon_reading (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                coupon_code      TEXT NOT NULL REFERENCES coupon(code) ON DELETE CASCADE,
                taken_on         TEXT NOT NULL,
                on_mv            REAL NOT NULL,
                disconnected_mv  REAL,
                dc_shunt_mv      REAL,
                ac_shunt_mv      REAL,
                ac_voltage_v     REAL,
                technician       TEXT NOT NULL DEFAULT '',
                comment          TEXT NOT NULL DEFAULT '',
                UNIQUE (coupon_code, taken_on)
            )
            """,
            "CREATE INDEX coupon_by_post ON coupon (test_point_code)",
            "CREATE INDEX coupon_reading_by_date ON coupon_reading (coupon_code, taken_on)",
        ),
    ),
    Migration(
        version=7,
        name="casings, crossings, bonds and isolating joints",
        statements=(
            """
            CREATE TABLE casing (
                code         TEXT PRIMARY KEY,
                line_code    TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                station_m    REAL NOT NULL,
                length_m     REAL NOT NULL DEFAULT 20 CHECK (length_m > 0),
                carries      TEXT NOT NULL DEFAULT '',
                installed_on TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE crossing (
                code             TEXT PRIMARY KEY,
                line_code        TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                station_m        REAL NOT NULL,
                foreign_operator TEXT NOT NULL,
                foreign_structure TEXT NOT NULL,
                bonded           INTEGER NOT NULL DEFAULT 0,
                description      TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE bond (
                code            TEXT PRIMARY KEY,
                line_code       TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                station_m       REAL NOT NULL,
                kind            TEXT NOT NULL,
                to_structure    TEXT NOT NULL,
                installed_on    TEXT NOT NULL,
                design_current_a REAL NOT NULL CHECK (design_current_a > 0),
                resistor_ohm    REAL,
                critical        INTEGER NOT NULL DEFAULT 0,
                description     TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE isolation_joint (
                code                   TEXT PRIMARY KEY,
                line_code              TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                station_m              REAL NOT NULL,
                kind                   TEXT NOT NULL,
                separates              TEXT NOT NULL,
                installed_on           TEXT NOT NULL,
                surge_protector_fitted INTEGER NOT NULL DEFAULT 0,
                description            TEXT NOT NULL DEFAULT ''
            )
            """,
            "CREATE INDEX casing_by_line ON casing (line_code, station_m)",
            "CREATE INDEX crossing_by_line ON crossing (line_code, station_m)",
            "CREATE INDEX bond_by_line ON bond (line_code, station_m)",
            "CREATE INDEX joint_by_line ON isolation_joint (line_code, station_m)",
        ),
    ),
    Migration(
        version=8,
        name="work orders",
        statements=(
            """
            CREATE TABLE work_order (
                code         TEXT PRIMARY KEY,
                line_code    TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                kind         TEXT NOT NULL,
                raised_on    TEXT NOT NULL,
                summary      TEXT NOT NULL,
                state        TEXT NOT NULL DEFAULT 'draft',
                planned_for  TEXT,
                completed_on TEXT,
                contractor   TEXT NOT NULL DEFAULT '',
                estimate     REAL,
                actual       REAL,
                notes        TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE work_order_finding (
                work_order_code TEXT NOT NULL
                                REFERENCES work_order(code) ON DELETE CASCADE,
                finding_code    TEXT NOT NULL REFERENCES finding(code) ON DELETE CASCADE,
                PRIMARY KEY (work_order_code, finding_code)
            )
            """,
            "CREATE INDEX work_order_by_line ON work_order (line_code, state)",
            "CREATE INDEX work_order_finding_by_finding ON work_order_finding (finding_code)",
        ),
    ),
    Migration(
        version=9,
        name="soil soundings",
        statements=(
            """
            CREATE TABLE sounding (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                line_code      TEXT NOT NULL REFERENCES line(code) ON DELETE CASCADE,
                station_m      REAL NOT NULL,
                measured_on    TEXT NOT NULL,
                technician     TEXT NOT NULL DEFAULT '',
                remark         TEXT NOT NULL DEFAULT '',
                UNIQUE (line_code, station_m, measured_on)
            )
            """,
            """
            CREATE TABLE sounding_reading (
                sounding_id    INTEGER NOT NULL REFERENCES sounding(id) ON DELETE CASCADE,
                spacing_m      REAL NOT NULL CHECK (spacing_m > 0),
                resistance_ohm REAL NOT NULL CHECK (resistance_ohm > 0),
                PRIMARY KEY (sounding_id, spacing_m)
            )
            """,
            "CREATE INDEX sounding_by_line ON sounding (line_code, station_m)",
        ),
    ),
    Migration(
        version=10,
        name="interference test history",
        statements=(
            """
            CREATE TABLE casing_test (
                casing_code   TEXT NOT NULL REFERENCES casing(code) ON DELETE CASCADE,
                tested_on     TEXT NOT NULL,
                pipe_on_mv    REAL NOT NULL,
                casing_on_mv  REAL NOT NULL,
                pipe_off_mv   REAL,
                casing_off_mv REAL,
                remark        TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (casing_code, tested_on)
            )
            """,
            """
            CREATE TABLE swing_test (
                crossing_code             TEXT NOT NULL
                                          REFERENCES crossing(code) ON DELETE CASCADE,
                tested_on                 TEXT NOT NULL,
                foreign_with_ours_on_mv   REAL NOT NULL,
                foreign_with_ours_off_mv  REAL NOT NULL,
                ours_on_mv                REAL,
                ours_off_mv               REAL,
                their_rectifier_interrupted INTEGER NOT NULL DEFAULT 0,
                remark                    TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (crossing_code, tested_on)
            )
            """,
            """
            CREATE TABLE bond_check (
                bond_code         TEXT NOT NULL REFERENCES bond(code) ON DELETE CASCADE,
                checked_on        TEXT NOT NULL,
                current_a         REAL NOT NULL,
                reversed_polarity INTEGER NOT NULL DEFAULT 0,
                remark            TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (bond_code, checked_on)
            )
            """,
            """
            CREATE TABLE isolation_test (
                joint_code              TEXT NOT NULL
                                        REFERENCES isolation_joint(code) ON DELETE CASCADE,
                tested_on               TEXT NOT NULL,
                our_side_mv             REAL NOT NULL,
                other_side_mv           REAL NOT NULL,
                surge_protector_removed INTEGER NOT NULL DEFAULT 0,
                technician              TEXT NOT NULL DEFAULT '',
                remark                  TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (joint_code, tested_on)
            )
            """,
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
