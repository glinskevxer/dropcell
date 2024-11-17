from __future__ import annotations

from collections.abc import Callable

from click.testing import Result

ADD_LINE = (
    "line",
    "add",
    "AL-2",
    "--name",
    "Ashfield lateral",
    "--operator",
    "Northmoor Gas",
    "--length",
    "18500 m",
    "--diameter",
    "323.9 mm",
    "--installed",
    "1974",
)

ADD_SEGMENT = (
    "segment",
    "add",
    "AL-2-001",
    "--line",
    "AL-2",
    "--from",
    "0+00.00",
    "--to",
    "600+00.00",
    "--coating",
    "coal_tar",
    "--diameter",
    "323.9 mm",
    "--wall",
    "6.35 mm",
    "--installed",
    "1974",
)


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post",
        "add",
        "TP-101",
        "--line",
        "AL-2",
        "--at",
        "10+00.00",
        "--installed",
        "1998-05-04",
    )


def test_the_programme_page_carries_every_figure(run: Callable[..., Result]) -> None:
    seed(run)
    run("post", "read", "TP-101", "--on", "-1120", "--off", "-905")
    printed = run("report", "kpi", "--line", "AL-2")
    assert printed.exit_code == 0
    assert "Programme, AL-2" in printed.output
    assert "posts never read" in printed.output
    assert "count, not a rate" in printed.output


def test_the_programme_page_needs_a_line_that_exists(run: Callable[..., Result]) -> None:
    assert run("report", "kpi", "--line", "ZZ-9").exit_code == 3


def test_a_post_with_too_few_readings_cannot_be_fitted(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("post", "read", "TP-101", "--on", "-1120", "--off", "-905")
    printed = run("report", "trend", "--line", "AL-2")
    assert "no post has enough readings" in printed.output


def test_a_post_with_a_history_gets_a_slope(run: Callable[..., Result]) -> None:
    seed(run)
    for year, off in ((2022, -1000), (2023, -950), (2024, -900)):
        run(
            "post",
            "read",
            "TP-101",
            "--on",
            "-1120",
            "--off",
            str(off),
            "--date",
            f"{year}-05-02",
        )
    printed = run("report", "trend", "--line", "AL-2")
    assert "TP-101" in printed.output
    assert "50.0" in printed.output
    assert "1 of 1 fitted posts" in printed.output


def test_a_flat_post_can_be_filtered_out(run: Callable[..., Result]) -> None:
    seed(run)
    for year in (2022, 2023, 2024):
        run(
            "post",
            "read",
            "TP-101",
            "--on",
            "-1120",
            "--off",
            "-905",
            "--date",
            f"{year}-05-02",
        )
    everything = run("report", "trend", "--line", "AL-2")
    assert "TP-101" in everything.output
    drifting = run("report", "trend", "--line", "AL-2", "--only-drifting")
    assert "no post has enough readings" in drifting.output


def test_the_horizon_decides_which_posts_are_counted(
    run: Callable[..., Result],
) -> None:
    seed(run)
    for year, off in ((2022, -1000), (2023, -999), (2024, -998)):
        run(
            "post",
            "read",
            "TP-101",
            "--on",
            "-1120",
            "--off",
            str(off),
            "--date",
            f"{year}-05-02",
        )
    near = run("report", "trend", "--line", "AL-2", "--horizon", "5")
    assert "0 of 1 fitted posts" in near.output
    far = run("report", "trend", "--line", "AL-2", "--horizon", "200")
    assert "1 of 1 fitted posts" in far.output


def test_the_trend_report_needs_a_line_that_exists(run: Callable[..., Result]) -> None:
    assert run("report", "trend", "--line", "ZZ-9").exit_code == 3
