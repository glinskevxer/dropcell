"""Reference electrodes, and the fact that a potential is meaningless without one.

Every structure to electrolyte potential is a difference against some half
cell. Buried pipe work is done against copper in saturated copper sulfate, so
that is what dropcell stores, but readings arrive against calomel from a lab,
against silver chloride from anything offshore, and against a zinc cell from a
permanent installation. A number without its electrode is not a reading, it is
a rumour.

Field cells also drift. Copper sulfate crystallises out, the porous plug fouls,
and the cell reads a hundred millivolts off with no outward sign. Crews check a
working cell against a lab standard on a schedule, and a check that has expired
puts every reading taken with it in doubt.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dropcell.errors import ValidationError


class Electrode(StrEnum):
    """The reference half cells dropcell knows how to convert between."""

    CSE = "cse"
    SCE = "sce"
    SILVER_CHLORIDE = "agcl"
    SILVER_CHLORIDE_SEAWATER = "agcl_sw"
    ZINC_SEAWATER = "zn_sw"


SHE_MILLIVOLTS: Final[dict[Electrode, float]] = {
    Electrode.CSE: 318.0,
    Electrode.SCE: 241.0,
    Electrode.SILVER_CHLORIDE: 197.0,
    Electrode.SILVER_CHLORIDE_SEAWATER: 250.0,
    Electrode.ZINC_SEAWATER: -780.0,
}

ELECTRODE_NAMES: Final[dict[Electrode, str]] = {
    Electrode.CSE: "copper/copper sulfate",
    Electrode.SCE: "saturated calomel",
    Electrode.SILVER_CHLORIDE: "silver/silver chloride, saturated KCl",
    Electrode.SILVER_CHLORIDE_SEAWATER: "silver/silver chloride, seawater",
    Electrode.ZINC_SEAWATER: "zinc, seawater",
}

DEFAULT_CALIBRATION_VALID_DAYS: Final = 180
CALIBRATION_REJECT_MV: Final = 20.0


def convert_potential(millivolts: float, source: Electrode, target: Electrode) -> float:
    """Restate a potential measured against one half cell against another."""
    return millivolts + SHE_MILLIVOLTS[source] - SHE_MILLIVOLTS[target]


def to_cse(millivolts: float, source: Electrode) -> float:
    """Restate a potential against copper/copper sulfate, which is what we store."""
    return convert_potential(millivolts, source, Electrode.CSE)


@dataclass(frozen=True)
class CellCheck:
    """One comparison of a working cell against a lab standard."""

    serial: str
    checked_on: dt.date
    offset_mv: float
    valid_days: int = DEFAULT_CALIBRATION_VALID_DAYS

    def __post_init__(self) -> None:
        if not self.serial.strip():
            raise ValidationError("cell serial cannot be blank")
        if self.valid_days <= 0:
            raise ValidationError("calibration validity must be positive", days=self.valid_days)

    @property
    def expires_on(self) -> dt.date:
        """The last day readings taken with this cell are backed by the check."""
        return self.checked_on + dt.timedelta(days=self.valid_days)

    @property
    def within_tolerance(self) -> bool:
        """Whether the cell was close enough to the standard to stay in service."""
        return abs(self.offset_mv) <= CALIBRATION_REJECT_MV

    def covers(self, reading_date: dt.date) -> bool:
        """Whether a reading taken on that date is backed by this check."""
        return self.checked_on <= reading_date <= self.expires_on

    def correct(self, millivolts: float) -> float:
        """Take the cell's own error back out of a reading it produced."""
        if not self.within_tolerance:
            raise ValidationError(
                "cell is outside tolerance and its readings cannot be corrected",
                serial=self.serial,
                offset_mv=self.offset_mv,
                limit_mv=CALIBRATION_REJECT_MV,
            )
        return millivolts - self.offset_mv
