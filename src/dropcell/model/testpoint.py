"""Test posts.

A test post is a plastic tube at the fence line with a terminal board in the
top and a bundle of wires running down to the pipe. It is the only place a
potential can be read without digging, so the whole monitoring programme is
built around where the posts are and what each wire in them goes to.

The readings taken at a post live in their own module. They outnumber the posts
by four orders of magnitude and their shape changes far more often.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.ids import normalise_code
from dropcell.stationing import Station


@dataclass(frozen=True)
class TestPoint:
    """One post on the line, with the leads it carries."""

    code: str
    line_code: str
    station: Station
    leads: frozenset[LeadKind]
    installed_on: dt.date
    description: str = field(default="", compare=False)
    permanent_reference_cell: bool = False
    in_service: bool = True
    removed_on: dt.date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalise_code(self.code, kind="test point code"))
        object.__setattr__(self, "line_code", normalise_code(self.line_code, kind="line code"))
        object.__setattr__(self, "leads", frozenset(self.leads))
        if not self.leads:
            raise ValidationError(
                "a test point with no leads is a plastic tube", code=self.code
            )
        if self.in_service and self.removed_on is not None:
            raise ValidationError("a post in service has not been removed", code=self.code)
        if not self.in_service and self.removed_on is None:
            raise ValidationError(
                "a post out of service needs the date it went", code=self.code
            )
        if self.removed_on is not None and self.removed_on < self.installed_on:
            raise ValidationError(
                "a post cannot be removed before it was installed", code=self.code
            )

    @property
    def reads_structure(self) -> bool:
        """Whether any lead here reads a potential on our own steel."""
        return any(lead.carries_structure_potential for lead in self.leads)

    def has(self, lead: LeadKind) -> bool:
        """Whether the post carries that lead."""
        return lead in self.leads

    def require_lead(self, lead: LeadKind) -> LeadKind:
        """Return the lead, or refuse it if this post does not carry it."""
        if lead not in self.leads:
            raise ValidationError(
                "this post does not carry that lead",
                code=self.code,
                lead=str(lead),
                leads=sorted(str(item) for item in self.leads),
            )
        return lead
