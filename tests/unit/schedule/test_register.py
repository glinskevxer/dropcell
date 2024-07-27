from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ValidationError
from dropcell.schedule.policy import STANDARD_POLICY, AssetKind, MonitoringPolicy
from dropcell.schedule.register import (
    AssetHistory,
    build_register,
    by_month,
    compliance_rate,
    due_within,
    overdue,
)

TODAY = dt.date(2025, 3, 14)


def post(code: str, *visits: dt.date, **kwargs: object) -> AssetHistory:
    return AssetHistory(
        code=code,
        kind=AssetKind.TEST_POINT,
        visits=tuple(visits),
        in_service_from=kwargs.get("in_service_from"),  # type: ignore[arg-type]
    )


def unit(code: str, *visits: dt.date) -> AssetHistory:
    return AssetHistory(code=code, kind=AssetKind.RECTIFIER, visits=tuple(visits))


def test_one_row_comes_out_per_rule_that_applies() -> None:
    register = build_register(STANDARD_POLICY, [post("TP-1", dt.date(2024, 5, 2))], as_of=TODAY)
    assert [item.rule_key for item in register] == ["test_point_annual"]


def test_an_asset_no_rule_covers_produces_nothing() -> None:
    crossing = AssetHistory(code="XG-4", kind=AssetKind.CROSSING)
    assert build_register(STANDARD_POLICY, [crossing], as_of=TODAY) == []


def test_an_asset_nobody_has_ever_visited_sorts_first() -> None:
    register = build_register(
        STANDARD_POLICY,
        [post("TP-1", dt.date(2023, 1, 2)), post("TP-2")],
        as_of=TODAY,
    )
    assert [item.asset_code for item in register] == ["TP-2", "TP-1"]


def test_the_most_overdue_asset_comes_before_the_less_overdue_one() -> None:
    register = build_register(
        STANDARD_POLICY,
        [post("TP-1", dt.date(2023, 10, 2)), post("TP-2", dt.date(2022, 1, 2))],
        as_of=TODAY,
    )
    assert [item.asset_code for item in register] == ["TP-2", "TP-1"]


def test_ties_are_broken_on_the_asset_code() -> None:
    same = dt.date(2024, 5, 2)
    register = build_register(
        STANDARD_POLICY, [post("TP-9", same), post("TP-1", same)], as_of=TODAY
    )
    assert [item.asset_code for item in register] == ["TP-1", "TP-9"]


def test_days_overdue_is_nought_for_work_that_is_not_late() -> None:
    register = build_register(STANDARD_POLICY, [post("TP-1", dt.date(2024, 5, 2))], as_of=TODAY)
    assert register[0].days_overdue == 0
    assert not register[0].overdue


def test_days_overdue_counts_up_once_the_date_has_gone() -> None:
    register = build_register(STANDARD_POLICY, [post("TP-1", dt.date(2023, 5, 2))], as_of=TODAY)
    assert register[0].days_overdue > 0
    assert register[0].overdue


def test_the_overdue_list_includes_anything_never_visited() -> None:
    register = build_register(
        STANDARD_POLICY,
        [post("TP-1", dt.date(2024, 5, 2)), post("TP-2")],
        as_of=TODAY,
    )
    assert [item.asset_code for item in overdue(register)] == ["TP-2"]


def test_a_window_takes_the_work_that_falls_inside_it() -> None:
    register = build_register(
        STANDARD_POLICY,
        [post("TP-1", dt.date(2024, 5, 2)), post("TP-2", dt.date(2024, 12, 1))],
        as_of=TODAY,
    )
    soon = due_within(register, 150, as_of=TODAY)
    assert [item.asset_code for item in soon] == ["TP-1"]


def test_a_window_always_includes_an_asset_with_no_due_date_at_all() -> None:
    register = build_register(STANDARD_POLICY, [post("TP-2")], as_of=TODAY)
    assert len(due_within(register, 0, as_of=TODAY)) == 1


def test_a_negative_window_is_refused() -> None:
    with pytest.raises(ValidationError):
        due_within([], -1, as_of=TODAY)


def test_grouping_by_month_buckets_on_the_due_date() -> None:
    register = build_register(
        STANDARD_POLICY,
        [post("TP-1", dt.date(2024, 5, 2)), post("TP-2", dt.date(2024, 5, 20))],
        as_of=TODAY,
    )
    grouped = by_month(register)
    assert set(grouped) == {(2025, 8)}
    assert len(grouped[(2025, 8)]) == 2


def test_grouping_leaves_out_anything_with_no_due_date() -> None:
    register = build_register(STANDARD_POLICY, [post("TP-2")], as_of=TODAY)
    assert by_month(register) == {}


def test_the_compliance_rate_is_the_share_of_rows_that_pass() -> None:
    register = build_register(
        STANDARD_POLICY,
        [post("TP-1", dt.date(2024, 5, 2)), post("TP-2", dt.date(2022, 5, 2))],
        as_of=TODAY,
    )
    assert compliance_rate(register) == pytest.approx(0.5)


def test_an_empty_register_is_vacuously_compliant() -> None:
    assert compliance_rate([]) == pytest.approx(1.0)


def test_rectifiers_and_posts_are_judged_on_their_own_rules() -> None:
    register = build_register(
        STANDARD_POLICY,
        [post("TP-1", dt.date(2024, 12, 2)), unit("RU-3", dt.date(2024, 12, 2))],
        as_of=TODAY,
    )
    by_code = {item.asset_code: item for item in register}
    assert by_code["TP-1"].rule_key == "test_point_annual"
    assert by_code["RU-3"].rule_key == "rectifier_bimonthly"
    assert by_code["RU-3"].overdue
    assert not by_code["TP-1"].overdue


def test_a_register_built_before_the_policy_took_effect_is_refused() -> None:
    policy = MonitoringPolicy(
        name="new",
        rules=STANDARD_POLICY.rules,
        effective_from=dt.date(2026, 1, 1),
    )
    with pytest.raises(ValidationError):
        build_register(policy, [post("TP-1")], as_of=TODAY)


def test_the_full_compliance_result_is_kept_on_every_row() -> None:
    register = build_register(STANDARD_POLICY, [post("TP-1", dt.date(2022, 5, 2))], as_of=TODAY)
    assert register[0].result.reasons()
