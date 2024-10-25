from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.model.enums import LeadKind
from dropcell.model.testpoint import TestPoint
from dropcell.stationing import Station


def make_post(**overrides: object) -> TestPoint:
    kwargs: dict[str, object] = {
        "code": "TP-114",
        "line_code": "AL-2",
        "station": Station(1245.5),
        "leads": frozenset({LeadKind.PIPE}),
        "installed_on": dt.date(1998, 5, 4),
    }
    kwargs.update(overrides)
    return TestPoint(**kwargs)  # type: ignore[arg-type]


def test_a_post_normalises_its_codes() -> None:
    post = make_post(code="tp 114", line_code="al-2")
    assert (post.code, post.line_code) == ("TP-114", "AL-2")


def test_a_post_with_no_leads_is_refused() -> None:
    with pytest.raises(ValidationError):
        make_post(leads=frozenset())


def test_a_post_with_only_a_foreign_lead_does_not_read_our_steel() -> None:
    assert not make_post(leads=frozenset({LeadKind.FOREIGN})).reads_structure
    assert make_post(leads=frozenset({LeadKind.FOREIGN, LeadKind.PIPE})).reads_structure


def test_asking_for_a_lead_the_post_does_not_have_names_what_it_does_have() -> None:
    post = make_post(leads=frozenset({LeadKind.PIPE, LeadKind.CASING}))
    assert post.require_lead(LeadKind.CASING) is LeadKind.CASING
    with pytest.raises(ValidationError) as caught:
        post.require_lead(LeadKind.COUPON)
    assert caught.value.detail["leads"] == ["casing", "pipe"]


def test_has_answers_without_raising() -> None:
    post = make_post()
    assert post.has(LeadKind.PIPE)
    assert not post.has(LeadKind.ANODE)


def test_a_lead_set_given_as_a_plain_set_is_frozen() -> None:
    post = make_post(leads={LeadKind.PIPE, LeadKind.BOND})
    assert isinstance(post.leads, frozenset)
