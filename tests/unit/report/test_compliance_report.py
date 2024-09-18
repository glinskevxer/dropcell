from __future__ import annotations

import datetime as dt

from dropcell.report.compliance import overdue_table, render_compliance, upcoming_table
from dropcell.schedule.policy import STANDARD_POLICY, AssetKind
from dropcell.schedule.register import AssetHistory, build_register

TODAY = dt.date(2025, 3, 14)


def post(code: str, *visits: dt.date) -> AssetHistory:
    return AssetHistory(code=code, kind=AssetKind.TEST_POINT, visits=tuple(visits))


def register(*histories: AssetHistory) -> list:  # type: ignore[type-arg]
    return build_register(STANDARD_POLICY, histories, as_of=TODAY)


def test_an_empty_register_reports_nothing_overdue() -> None:
    assert "nothing overdue" in overdue_table([]).render()


def test_a_late_asset_appears_with_its_last_visit_and_how_late_it_is() -> None:
    rendered = overdue_table(register(post("TP-1", dt.date(2023, 5, 2)))).render()
    assert "TP-1" in rendered
    assert "2023-05-02" in rendered
    assert "test_point_annual" in rendered


def test_an_asset_nobody_has_visited_says_so_rather_than_carrying_a_date() -> None:
    rendered = overdue_table(register(post("TP-2"))).render()
    assert "never" in rendered


def test_an_asset_inside_its_interval_is_not_on_the_overdue_table() -> None:
    rendered = overdue_table(register(post("TP-1", dt.date(2024, 12, 1)))).render()
    assert "nothing overdue" in rendered


def test_the_upcoming_table_takes_the_work_inside_the_window() -> None:
    rendered = upcoming_table(
        register(post("TP-1", dt.date(2024, 5, 2))), as_of=TODAY, days=200
    ).render()
    assert "TP-1" in rendered
    assert "2025-08-01" in rendered


def test_the_upcoming_table_leaves_the_overdue_work_to_the_other_table() -> None:
    rendered = upcoming_table(
        register(post("TP-1", dt.date(2022, 5, 2))), as_of=TODAY, days=400
    ).render()
    assert "nothing due in the window" in rendered


def test_a_short_window_finds_nothing() -> None:
    rendered = upcoming_table(
        register(post("TP-1", dt.date(2024, 12, 1))), as_of=TODAY, days=5
    ).render()
    assert "nothing due in the window" in rendered


def test_the_whole_report_carries_both_tables_and_the_rate() -> None:
    rendered = render_compliance(
        register(post("TP-1", dt.date(2022, 5, 2)), post("TP-2", dt.date(2024, 12, 1))),
        as_of=TODAY,
        days=400,
    )
    assert "Monitoring compliance" in rendered
    assert "as at 2025-03-14" in rendered
    assert "2 asset and rule pairs, 1 overdue" in rendered
    assert "compliance rate 50.0%" in rendered
    assert "Overdue" in rendered
    assert "Falling due" in rendered


def test_the_rate_line_says_what_it_is_a_rate_of() -> None:
    rendered = render_compliance(register(post("TP-1", dt.date(2024, 12, 1))), as_of=TODAY)
    assert "both halves of their rule" in rendered


def test_the_title_can_be_changed() -> None:
    rendered = render_compliance([], as_of=TODAY, title="AL-2 compliance")
    assert rendered.startswith("AL-2 compliance")


def test_an_empty_register_still_renders_a_whole_report() -> None:
    rendered = render_compliance([], as_of=TODAY)
    assert "0 asset and rule pairs" in rendered
    assert "compliance rate 100.0%" in rendered
