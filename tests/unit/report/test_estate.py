from __future__ import annotations

import datetime as dt

import pytest

from dropcell.report.estate import LineSummary, render_estate

TODAY = dt.date(2025, 3, 14)


def summary(**overrides: object) -> LineSummary:
    kwargs: dict[str, object] = {
        "code": "AL-2",
        "name": "Ashfield lateral",
        "operator": "Northmoor Gas",
        "length_m": 18_500.0,
        "posts": 10,
        "judged": 10,
        "protected": 10,
        "unread": 0,
        "overdue": 0,
        "open_findings": 0,
    }
    kwargs.update(overrides)
    return LineSummary(**kwargs)  # type: ignore[arg-type]


def test_a_line_with_no_posts_has_no_rate() -> None:
    line = summary(posts=0, judged=0, protected=0)
    assert line.rate is None
    assert line.state == "no posts"


def test_a_line_with_posts_but_no_readings_says_never_read() -> None:
    assert summary(judged=0, protected=0, unread=10).state == "never read"


def test_a_line_half_unread_says_so() -> None:
    line = summary(posts=10, judged=5, protected=5, unread=5)
    assert line.state == "half unread"


def test_a_line_mostly_failing_says_under_criterion() -> None:
    assert summary(protected=5).state == "under criterion"


def test_a_line_passing_but_behind_says_behind() -> None:
    assert summary(overdue=3).state == "behind"


def test_a_line_with_nothing_wrong_says_in_hand() -> None:
    assert summary().state == "in hand"


def test_the_rate_is_over_judged_posts() -> None:
    assert summary(judged=8, protected=4, unread=2).rate == pytest.approx(0.5)


def test_lines_nobody_has_built_sort_first() -> None:
    built = summary(code="AL-2")
    unbuilt = summary(code="ZZ-9", posts=0, judged=0, protected=0)
    rendered = render_estate([built, unbuilt], as_of=TODAY)
    assert rendered.index("ZZ-9") < rendered.index("AL-2")


def test_the_worst_rate_comes_first_among_the_built_lines() -> None:
    good = summary(code="AL-2")
    bad = summary(code="BR-9", protected=3)
    rendered = render_estate([good, bad], as_of=TODAY)
    assert rendered.index("BR-9") < rendered.index("AL-2")


def test_a_short_line_and_a_long_one_are_ranked_on_rate_not_count() -> None:
    short_line = summary(code="SH-1", length_m=2000.0, posts=4, judged=4, protected=0)
    long_line = summary(code="LO-1", length_m=20000.0, posts=40, judged=40, protected=36)
    rendered = render_estate([long_line, short_line], as_of=TODAY)
    assert rendered.index("SH-1") < rendered.index("LO-1")


def test_the_page_can_be_grouped_by_operator() -> None:
    rendered = render_estate(
        [summary(), summary(code="VW-1", operator="Vale Water")],
        as_of=TODAY,
        by_operator=True,
    )
    assert rendered.count("Northmoor Gas") == 1
    assert rendered.index("Northmoor Gas") < rendered.index("Vale Water")


def test_the_ungrouped_page_repeats_the_operator_on_every_row() -> None:
    rendered = render_estate([summary(), summary(code="BR-9")], as_of=TODAY)
    assert rendered.count("Northmoor Gas") == 2


def test_the_operators_are_counted() -> None:
    rendered = render_estate(
        [summary(), summary(code="VW-1", operator="Vale Water")], as_of=TODAY
    )
    assert "2 lines across 2 operators" in rendered


def test_grouping_keeps_the_worst_line_first_inside_an_operator() -> None:
    good = summary(code="AL-2")
    bad = summary(code="BR-9", protected=3)
    rendered = render_estate([good, bad], as_of=TODAY, by_operator=True)
    assert rendered.index("BR-9") < rendered.index("AL-2")


def test_the_page_counts_the_lines_nobody_has_built() -> None:
    rendered = render_estate(
        [summary(), summary(code="ZZ-9", posts=0, judged=0, protected=0)], as_of=TODAY
    )
    assert "1 with no posts on them at all" in rendered


def test_the_page_adds_the_estate_up() -> None:
    rendered = render_estate(
        [summary(), summary(code="BR-9", judged=10, protected=5)], as_of=TODAY
    )
    assert "15 of 20 judged posts" in rendered
    assert "37.0 km" in rendered


def test_an_estate_with_nothing_read_does_not_divide_by_nothing() -> None:
    rendered = render_estate([summary(posts=0, judged=0, protected=0)], as_of=TODAY)
    assert "0 of 0 judged posts" in rendered
    assert "0.0%" in rendered


def test_an_empty_estate_says_so() -> None:
    assert "no lines in the register" in render_estate([], as_of=TODAY)


def test_zero_counts_are_left_blank_rather_than_printed() -> None:
    rendered = render_estate([summary()], as_of=TODAY)
    row = [line for line in rendered.splitlines() if "AL-2" in line][0]
    assert "in hand" in row
