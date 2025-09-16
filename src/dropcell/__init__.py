"""Cathodic protection monitoring and compliance for buried steel pipelines.

Everything under here is importable, and most of it should not be imported by
anything outside this package. What is named below is the part that is meant to
be used from another program: the records, the criteria, the register, and the
handful of functions that turn one into the other.

The rule for anything on this list is that it does not change shape without a
version behind it. The rule for everything else is that it can change on any
Tuesday, which is what makes the rest of the package possible to work on.

The command line is not on the list. It is an interface for people, its output
is meant to be readable rather than parsed, and anything that wants the numbers
should use the JSON the reports emit or the objects named here.
"""

from __future__ import annotations

from dropcell.analysis.line import LineAssessment, PostAssessment, assess_line
from dropcell.config import Settings, load_or_default
from dropcell.criteria.base import Assessment, Evidence, Outcome
from dropcell.criteria.build import select_for
from dropcell.criteria.evaluate import CriterionSet, PointVerdict
from dropcell.errors import (
    ConflictError,
    DropcellError,
    IngestError,
    MigrationError,
    NotFoundError,
    PolicyError,
    StoreError,
    UnitError,
    ValidationError,
)
from dropcell.findings.finding import Finding, FindingKind, FindingState
from dropcell.model.enums import (
    ClassLocation,
    CoatingType,
    Commodity,
    LeadKind,
    LineStatus,
    ProtectionMethod,
)
from dropcell.model.line import Line
from dropcell.model.reading import Reading
from dropcell.model.segment import Segment
from dropcell.model.testpoint import TestPoint
from dropcell.schedule.policy import STANDARD_POLICY, AssetKind, MonitoringPolicy
from dropcell.schedule.register import AssetHistory, DueItem, build_register
from dropcell.stationing import Convention, Station, StationRange
from dropcell.store.database import Database
from dropcell.store.migrations import latest_version, migrate, open_register

__version__ = "1.0.0"

__all__ = [
    "STANDARD_POLICY",
    "Assessment",
    "AssetHistory",
    "AssetKind",
    "ClassLocation",
    "CoatingType",
    "Commodity",
    "ConflictError",
    "Convention",
    "CriterionSet",
    "Database",
    "DropcellError",
    "DueItem",
    "Evidence",
    "Finding",
    "FindingKind",
    "FindingState",
    "IngestError",
    "LeadKind",
    "Line",
    "LineAssessment",
    "LineStatus",
    "MigrationError",
    "MonitoringPolicy",
    "NotFoundError",
    "Outcome",
    "PointVerdict",
    "PolicyError",
    "PostAssessment",
    "ProtectionMethod",
    "Reading",
    "Segment",
    "Settings",
    "Station",
    "StationRange",
    "StoreError",
    "TestPoint",
    "UnitError",
    "ValidationError",
    "__version__",
    "assess_line",
    "build_register",
    "latest_version",
    "load_or_default",
    "migrate",
    "open_register",
    "select_for",
]
