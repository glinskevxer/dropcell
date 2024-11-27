"""The file formats dropcell ships knowing about.

Every one of these was written by looking at a real export and listing the
headers it uses, including the ones that are the same thing spelled three ways.
Adding a contractor is adding a profile here, not writing code, and that is the
point of the exercise.

The header lists are deliberately generous. A profile that only accepts the
exact spelling one version of one package produced will start failing the week
that package is updated, and the failure will look like a broken file rather
than a stale profile.
"""

from __future__ import annotations

from dropcell.errors import IngestError
from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile

CIS_PROFILE = MappingProfile(
    name="cis",
    description="close interval survey, one row per step",
    columns=(
        ColumnMapping(
            "station",
            FieldType.STATION,
            ("Station", "Chainage", "Sta", "Distance", "Location"),
        ),
        ColumnMapping(
            "on_mv",
            FieldType.POTENTIAL,
            ("P/S On", "On", "On Potential", "On_mV", "Pipe to Soil On", "Von"),
        ),
        ColumnMapping(
            "off_mv",
            FieldType.POTENTIAL,
            ("P/S Off", "Off", "Instant Off", "Off Potential", "Off_mV", "Voff"),
            required=False,
        ),
        ColumnMapping(
            "remark",
            FieldType.TEXT,
            ("Remark", "Comment", "Note", "Notes"),
            required=False,
            default="",
        ),
    ),
)

ANNUAL_PROFILE = MappingProfile(
    name="annual",
    description="annual test point survey, one row per lead visit",
    columns=(
        ColumnMapping(
            "test_point_code",
            FieldType.TEXT,
            ("Test Point", "TP", "Post", "Test Post", "TP No", "Station ID"),
        ),
        ColumnMapping("taken_on", FieldType.DATE, ("Date", "Read Date", "Survey Date")),
        ColumnMapping("lead", FieldType.TEXT, ("Lead", "Wire", "Conductor"), required=False),
        ColumnMapping("on_mv", FieldType.POTENTIAL, ("On", "P/S On", "On Potential")),
        ColumnMapping(
            "off_mv",
            FieldType.POTENTIAL,
            ("Off", "P/S Off", "Instant Off"),
            required=False,
        ),
        ColumnMapping(
            "native_mv",
            FieldType.POTENTIAL,
            ("Native", "Static", "Depolarised"),
            required=False,
        ),
        ColumnMapping(
            "cell_serial", FieldType.TEXT, ("Cell", "Cell Serial", "Half Cell"), required=False
        ),
        ColumnMapping(
            "technician",
            FieldType.TEXT,
            ("Technician", "Tech", "Surveyor", "By"),
            required=False,
        ),
        ColumnMapping(
            "comment", FieldType.TEXT, ("Comment", "Remark", "Note"), required=False, default=""
        ),
    ),
)

RECTIFIER_PROFILE = MappingProfile(
    name="rectifier",
    description="rectifier check sheet, one row per visit",
    columns=(
        ColumnMapping("rectifier_tag", FieldType.TEXT, ("Rectifier", "Unit", "Tag", "TR")),
        ColumnMapping("checked_on", FieldType.DATE, ("Date", "Check Date", "Read Date")),
        ColumnMapping(
            "output_voltage_v", FieldType.VOLTAGE, ("Volts", "Output Volts", "DC Volts", "V")
        ),
        ColumnMapping(
            "output_current_a", FieldType.CURRENT, ("Amps", "Output Amps", "DC Amps", "A")
        ),
        ColumnMapping(
            "coarse_tap", FieldType.INTEGER, ("Coarse", "Coarse Tap"), required=False
        ),
        ColumnMapping("fine_tap", FieldType.INTEGER, ("Fine", "Fine Tap"), required=False),
        ColumnMapping(
            "hour_meter", FieldType.NUMBER, ("Hours", "Hour Meter", "Run Hours"), required=False
        ),
        ColumnMapping(
            "technician", FieldType.TEXT, ("Technician", "Tech", "By"), required=False
        ),
        ColumnMapping(
            "comment", FieldType.TEXT, ("Comment", "Remark", "Note"), required=False, default=""
        ),
    ),
)

DCVG_PROFILE = MappingProfile(
    name="dcvg",
    description="gradient survey indications, one row per defect",
    columns=(
        ColumnMapping("station", FieldType.STATION, ("Station", "Chainage", "Location")),
        ColumnMapping(
            "found_on",
            FieldType.DATE,
            ("Date", "Survey Date"),
            required=False,
        ),
        ColumnMapping(
            "gradient_mv", FieldType.POTENTIAL, ("Gradient", "Defect mV", "dV", "Signal")
        ),
        ColumnMapping(
            "section_shift_mv",
            FieldType.POTENTIAL,
            ("Section Shift", "Total Shift", "Remote Earth Shift", "Delta V"),
        ),
        ColumnMapping(
            "anodic",
            FieldType.FLAG,
            ("Anodic", "Anodic Indication", "Current Leaving"),
            required=False,
        ),
        ColumnMapping(
            "remark", FieldType.TEXT, ("Remark", "Comment", "Note"), required=False, default=""
        ),
    ),
)

SOIL_PROFILE = MappingProfile(
    name="soil",
    description="four pin resistivity soundings, one row per spacing",
    columns=(
        ColumnMapping("station", FieldType.STATION, ("Station", "Chainage", "Location")),
        ColumnMapping("measured_on", FieldType.DATE, ("Date", "Survey Date")),
        ColumnMapping("spacing_m", FieldType.LENGTH, ("Spacing", "Pin Spacing", "A")),
        ColumnMapping(
            "resistance_ohm", FieldType.NUMBER, ("Resistance", "R", "Ohms", "Meter Reading")
        ),
        ColumnMapping(
            "remark", FieldType.TEXT, ("Remark", "Comment", "Note"), required=False, default=""
        ),
    ),
)

PROFILES: dict[str, MappingProfile] = {
    profile.name: profile
    for profile in (
        CIS_PROFILE,
        ANNUAL_PROFILE,
        RECTIFIER_PROFILE,
        DCVG_PROFILE,
        SOIL_PROFILE,
    )
}


def get_profile(name: str) -> MappingProfile:
    """Look a profile up by name, refusing one that is not shipped."""
    try:
        return PROFILES[name]
    except KeyError:
        raise IngestError(
            "no import profile by that name", name=name, known=sorted(PROFILES)
        ) from None


def profile_names() -> list[str]:
    """Every profile this build ships, for a help listing."""
    return sorted(PROFILES)
