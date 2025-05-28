"""Settings that belong to an operator rather than to the code.

The thresholds in here are written into standards, and different operators work
to different ones. The criterion is minus eight hundred and fifty almost
everywhere and minus nine hundred and fifty in some ground; the AC density
bands move between one standard and the next; the reach a post is credited with
is a local judgement that varies by a factor of four between a rural
transmission line and a distribution network in a city.

Hard coding those means every operator who is not the one this was written for
gets silently wrong answers. Making them command line options means somebody
has to remember to pass them, which is the same problem with an extra step.
They go in a file, the file is read once, and the values it does not carry keep
the defaults the code already had.

TOML is read with the standard library, so this adds no dependency. Anything
the file carries that this build does not know is refused rather than ignored,
because a misspelled key that is quietly dropped is a setting somebody believes
is in force.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from dropcell.criteria.ac import AC_DENSITY_HIGH_RISK, AC_DENSITY_LOW_RISK
from dropcell.criteria.decay import MINIMUM_DECAY_MV
from dropcell.criteria.limits import DISBONDMENT_LIMIT_MV
from dropcell.criteria.potential import DEFAULT_PROTECTION_MV
from dropcell.errors import ValidationError
from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile

DEFAULT_REACH_M = 1600.0
CONFIG_NAMES = ("dropcell.toml", ".dropcell.toml")


@dataclass(frozen=True)
class Settings:
    """Everything an operator can move without changing the code."""

    register: str = "cp.sqlite"
    operator: str = ""
    contact: str = ""
    protection_mv: float = DEFAULT_PROTECTION_MV
    decay_mv: float = MINIMUM_DECAY_MV
    over_protection_mv: float = DISBONDMENT_LIMIT_MV
    ac_low_risk_a_per_m2: float = AC_DENSITY_LOW_RISK
    ac_high_risk_a_per_m2: float = AC_DENSITY_HIGH_RISK
    post_reach_m: float = DEFAULT_REACH_M
    dig_budget: int | None = None
    profiles: tuple[MappingProfile, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.protection_mv >= 0:
            raise ValidationError(
                "a protection criterion is a negative potential",
                protection_mv=self.protection_mv,
            )
        if self.over_protection_mv >= self.protection_mv:
            raise ValidationError(
                "the over protection limit has to sit below the criterion",
                protection_mv=self.protection_mv,
                over_protection_mv=self.over_protection_mv,
            )
        if self.decay_mv <= 0:
            raise ValidationError("the decay criterion is a positive shift")
        if self.ac_high_risk_a_per_m2 <= self.ac_low_risk_a_per_m2:
            raise ValidationError(
                "the high risk AC band has to sit above the low risk one",
                low=self.ac_low_risk_a_per_m2,
                high=self.ac_high_risk_a_per_m2,
            )
        if self.post_reach_m <= 0:
            raise ValidationError("a post has to speak for some length")
        if self.dig_budget is not None and self.dig_budget < 0:
            raise ValidationError("a dig budget cannot be negative")
        seen: set[str] = set()
        for profile in self.profiles:
            if profile.name in seen:
                raise ValidationError("two profiles share a name", name=profile.name)
            seen.add(profile.name)

    def profile(self, name: str) -> MappingProfile | None:
        """One profile the settings file added, if it added it."""
        for candidate in self.profiles:
            if candidate.name == name:
                return candidate
        return None


def known_keys() -> frozenset[str]:
    """Every setting this build understands."""
    return frozenset(field.name for field in fields(Settings))


def parse_profile(table: dict[str, Any]) -> MappingProfile:
    """Build one import profile from a table in the settings file.

    An operator with a contractor this build has never heard of should not have
    to wait for a release to load their files. The profile is the same data the
    shipped ones are, so it can be written down in the settings file, and the
    reader cannot tell the difference.
    """
    try:
        name = str(table["name"])
        columns = table["columns"]
    except KeyError as exc:
        raise ValidationError("a profile needs a name and columns", missing=str(exc)) from None
    if not isinstance(columns, list):
        raise ValidationError("the columns of a profile are a list of tables", name=name)
    built: list[ColumnMapping] = []
    for entry in columns:
        if not isinstance(entry, dict):
            raise ValidationError("each column is a table", name=name)
        unknown = sorted(set(entry) - {"field", "type", "headers", "required", "default"})
        if unknown:
            raise ValidationError("a column carries keys this build ignores", unknown=unknown)
        try:
            field_type = FieldType(str(entry.get("type", "text")))
        except ValueError:
            raise ValidationError(
                "that is not a column type this build knows",
                type=entry.get("type"),
                known=sorted(str(item) for item in FieldType),
            ) from None
        built.append(
            ColumnMapping(
                field_name=str(entry.get("field", "")),
                field_type=field_type,
                headers=tuple(str(item) for item in entry.get("headers", ())),
                required=bool(entry.get("required", True)),
                default=None if entry.get("default") is None else str(entry["default"]),
            )
        )
    return MappingProfile(
        name=name,
        columns=tuple(built),
        delimiter=str(table.get("delimiter", ",")),
        encoding=str(table.get("encoding", "utf-8")),
        skip_rows=int(table.get("skip_rows", 0)),
        description=str(table.get("description", "from the settings file")),
    )


def from_mapping(values: dict[str, Any]) -> Settings:
    """Build settings from a mapping, refusing anything unrecognised."""
    unknown = sorted(set(values) - known_keys())
    if unknown:
        raise ValidationError(
            "this build does not know those settings",
            unknown=unknown,
            known=sorted(known_keys()),
        )
    prepared = dict(values)
    raw_profiles = prepared.pop("profiles", None)
    if raw_profiles is not None:
        if not isinstance(raw_profiles, list):
            raise ValidationError("profiles are a list of tables")
        prepared["profiles"] = tuple(parse_profile(item) for item in raw_profiles)
    return Settings(**prepared)


def load(path: Path | str) -> Settings:
    """Read a settings file."""
    target = Path(path)
    try:
        payload = target.read_bytes()
    except OSError as exc:
        raise ValidationError("cannot read that settings file", path=str(target)) from exc
    try:
        parsed = tomllib.loads(payload.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(
            "that settings file is not readable TOML", path=str(target), reason=str(exc)
        ) from exc
    section = parsed.get("dropcell", parsed)
    if not isinstance(section, dict):
        raise ValidationError("the dropcell section has to be a table", path=str(target))
    return from_mapping(section)


def find(start: Path | str = ".") -> Path | None:
    """Look for a settings file here and in every directory above."""
    here = Path(start).resolve()
    for directory in (here, *here.parents):
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def load_or_default(path: Path | str | None = None, *, start: Path | str = ".") -> Settings:
    """Read the settings file that was named, or the nearest one, or the defaults."""
    if path is not None:
        return load(path)
    found = find(start)
    return Settings() if found is None else load(found)
