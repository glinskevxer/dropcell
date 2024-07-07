from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import PolicyError
from dropcell.schedule.policy import (
    RECTIFIER_BIMONTHLY,
    STANDARD_POLICY,
    TEST_POINT_ANNUAL,
    AssetKind,
    MonitoringPolicy,
    MonitoringRule,
)


def rule(**overrides: object) -> MonitoringRule:
    kwargs: dict[str, object] = {
        "key": "test_rule",
        "asset_kind": AssetKind.TEST_POINT,
        "times_per_calendar_year": 1,
        "maximum_interval_days": 456,
    }
    kwargs.update(overrides)
    return MonitoringRule(**kwargs)  # type: ignore[arg-type]


def test_a_rule_needs_a_key() -> None:
    with pytest.raises(PolicyError):
        rule(key="  ")


def test_a_rule_requiring_nothing_per_year_is_refused() -> None:
    with pytest.raises(PolicyError):
        rule(times_per_calendar_year=0)


def test_a_rule_with_no_interval_is_refused() -> None:
    with pytest.raises(PolicyError):
        rule(maximum_interval_days=0)


def test_an_interval_over_two_years_is_refused() -> None:
    with pytest.raises(PolicyError) as caught:
        rule(times_per_calendar_year=1, maximum_interval_days=900)
    assert caught.value.detail["days"] == 900


def test_the_fifteen_month_interval_that_real_policies_use_is_accepted() -> None:
    assert rule(times_per_calendar_year=1, maximum_interval_days=456)


def test_the_nominal_interval_is_what_the_count_implies_on_its_own() -> None:
    assert TEST_POINT_ANNUAL.nominal_interval_days == pytest.approx(365.25)
    assert RECTIFIER_BIMONTHLY.nominal_interval_days == pytest.approx(60.875)


def test_neither_standard_rule_has_the_interval_as_the_binding_half() -> None:
    assert not TEST_POINT_ANNUAL.interval_is_binding
    assert not RECTIFIER_BIMONTHLY.interval_is_binding


def test_a_tighter_policy_can_make_the_interval_the_binding_half() -> None:
    tight = rule(times_per_calendar_year=1, maximum_interval_days=180)
    assert tight.interval_is_binding


def test_the_next_due_date_comes_off_the_interval_rule() -> None:
    assert TEST_POINT_ANNUAL.next_due(dt.date(2024, 5, 2)) == dt.date(2025, 8, 1)
    assert RECTIFIER_BIMONTHLY.next_due(dt.date(2025, 1, 6)) == dt.date(2025, 3, 22)


def test_a_policy_with_no_rules_is_refused() -> None:
    with pytest.raises(PolicyError):
        MonitoringPolicy(name="empty", rules=(), effective_from=dt.date(2020, 1, 1))


def test_two_rules_sharing_a_key_are_refused() -> None:
    with pytest.raises(PolicyError) as caught:
        MonitoringPolicy(
            name="clash",
            rules=(rule(), rule(maximum_interval_days=300)),
            effective_from=dt.date(2020, 1, 1),
        )
    assert caught.value.detail["key"] == "test_rule"


def test_a_rule_can_be_fetched_by_key() -> None:
    assert STANDARD_POLICY.rule("rectifier_bimonthly") is RECTIFIER_BIMONTHLY


def test_an_unknown_key_lists_the_ones_that_exist() -> None:
    with pytest.raises(PolicyError) as caught:
        STANDARD_POLICY.rule("wishful")
    assert "rectifier_bimonthly" in caught.value.detail["known"]


def test_rules_can_be_filtered_by_what_they_apply_to() -> None:
    posts = STANDARD_POLICY.for_asset(AssetKind.TEST_POINT)
    assert [item.key for item in posts] == ["test_point_annual"]
    assert STANDARD_POLICY.for_asset(AssetKind.CROSSING) == ()


def test_a_policy_only_covers_dates_from_when_it_took_effect() -> None:
    policy = MonitoringPolicy(name="new", rules=(rule(),), effective_from=dt.date(2024, 1, 1))
    assert policy.covers(dt.date(2024, 1, 1))
    assert policy.covers(dt.date(2025, 6, 1))
    assert not policy.covers(dt.date(2023, 12, 31))


def test_the_standard_policy_carries_both_halves_of_every_rule() -> None:
    for item in STANDARD_POLICY.rules:
        assert item.times_per_calendar_year >= 1
        assert item.maximum_interval_days >= 1


def test_critical_bonds_are_on_the_rectifier_cycle_and_ordinary_ones_are_not() -> None:
    critical = STANDARD_POLICY.for_asset(AssetKind.CRITICAL_BOND)
    assert critical[0].maximum_interval_days == RECTIFIER_BIMONTHLY.maximum_interval_days
    assert STANDARD_POLICY.for_asset(AssetKind.ORDINARY_BOND) == ()
