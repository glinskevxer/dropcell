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
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from dropcell.criteria.ac import AC_DENSITY_HIGH_RISK, AC_DENSITY_LOW_RISK
from dropcell.criteria.decay import MINIMUM_DECAY_MV
from dropcell.criteria.limits import DISBONDMENT_LIMIT_MV
from dropcell.criteria.potential import DEFAULT_PROTECTION_MV
from dropcell.errors import ValidationError

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


def known_keys() -> frozenset[str]:
    """Every setting this build understands."""
    return frozenset(field.name for field in fields(Settings))


def from_mapping(values: dict[str, Any]) -> Settings:
    """Build settings from a mapping, refusing anything unrecognised."""
    unknown = sorted(set(values) - known_keys())
    if unknown:
        raise ValidationError(
            "this build does not know those settings",
            unknown=unknown,
            known=sorted(known_keys()),
        )
    return Settings(**values)


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
