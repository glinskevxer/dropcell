"""Error types raised across dropcell.

Every failure carries a short machine readable ``code`` plus a ``detail``
mapping. The CLI prints the code and the mapping, the store writes both into
its audit rows, and tests assert on the code instead of on message text, which
lets wording change without breaking a suite.
"""

from __future__ import annotations

from typing import Any


class DropcellError(Exception):
    """Base class for every error this package raises deliberately."""

    code = "dropcell_error"

    def __init__(self, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.message = message
        self.detail: dict[str, Any] = dict(detail)

    def __str__(self) -> str:
        if not self.detail:
            return self.message
        pairs = ", ".join(f"{key}={value!r}" for key, value in sorted(self.detail.items()))
        return f"{self.message} ({pairs})"

    def as_dict(self) -> dict[str, Any]:
        """Render the error in the shape the CLI and the audit log both use."""
        return {"code": self.code, "message": self.message, "detail": dict(self.detail)}


class ValidationError(DropcellError):
    """A value did not satisfy a rule that is checked before anything is stored."""

    code = "validation"


class UnitError(ValidationError):
    """A quantity was given in a unit this call cannot accept."""

    code = "unit"


class StationError(ValidationError):
    """A stationing string could not be parsed, or a range ran backwards."""

    code = "station"


class NotFoundError(DropcellError):
    """A record was looked up by a key that nothing in the store carries."""

    code = "not_found"


class ConflictError(DropcellError):
    """Writing a record would break a uniqueness or ordering guarantee."""

    code = "conflict"


class PolicyError(DropcellError):
    """A monitoring policy is internally inconsistent or does not cover a case."""

    code = "policy"


class IngestError(DropcellError):
    """A vendor file could not be read, mapped, or reconciled."""

    code = "ingest"

    def __init__(self, message: str, *, row: int | None = None, **detail: Any) -> None:
        super().__init__(message, **detail)
        self.row = row
        if row is not None:
            self.detail["row"] = row


class StoreError(DropcellError):
    """The SQLite layer refused an operation for a reason the caller can act on."""

    code = "store"


class MigrationError(StoreError):
    """The schema on disk does not match what this build of dropcell expects."""

    code = "migration"
