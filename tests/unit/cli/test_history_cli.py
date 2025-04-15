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
    for code, station in (("TP-1", "10+00.00"), ("TP-2", "150+00.00")):
        run("post", "add", code, "--line", "AL-2", "--at", station, "--installed", "1998-05-04")


def read(run: Callable[..., Result], code: str, date: str, off: str) -> None:
    run("post", "read", code, "--on", "-1120", "--off", off, "--date", date)


def test_a_line_with_one_year_of_readings_cannot_be_compared(
    run: Callable[..., Result],
) -> None:
    seed(run)
    read(run, "TP-1", "2024-05-02", "-905")
    result = run("report", "history", "--line", "AL-2")
    assert result.exit_code == 0
    assert "fewer than two years" in result.output
    assert "years with readings: 2024" in result.output


def test_a_line_with_no_readings_says_so(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "history", "--line", "AL-2")
    assert "years with readings: none" in result.output


def test_the_two_most_recent_years_are_compared_by_default(
    run: Callable[..., Result],
) -> None:
    seed(run)
    read(run, "TP-1", "2022-05-02", "-905")
    read(run, "TP-1", "2023-05-02", "-905")
    read(run, "TP-1", "2024-05-02", "-800")
    result = run("report", "history", "--line", "AL-2")
    assert "AL-2 2023 to 2024" in result.output
    assert "net -1" in result.output


def test_a_post_that_lost_criterion_is_on_the_page(
    run: Callable[..., Result],
) -> None:
    seed(run)
    read(run, "TP-1", "2023-05-02", "-905")
    read(run, "TP-1", "2024-05-02", "-800")
    result = run("report", "history", "--line", "AL-2")
    lost = result.output.split("Lost criterion")[1].split("Gained criterion")[0]
    assert "TP-1" in lost
    assert "+105" in lost


def test_a_post_that_gained_criterion_is_on_the_page(
    run: Callable[..., Result],
) -> None:
    seed(run)
    read(run, "TP-1", "2023-05-02", "-800")
    read(run, "TP-1", "2024-05-02", "-905")
    result = run("report", "history", "--line", "AL-2")
    gained = result.output.split("Gained criterion")[1]
    assert "TP-1" in gained


def test_the_years_can_be_named(run: Callable[..., Result]) -> None:
    seed(run)
    read(run, "TP-1", "2021-05-02", "-905")
    read(run, "TP-1", "2024-05-02", "-800")
    result = run("report", "history", "--line", "AL-2", "--from", "2021", "--to", "2024")
    assert "AL-2 2021 to 2024" in result.output


def test_a_post_read_in_only_one_year_is_counted_separately(
    run: Callable[..., Result],
) -> None:
    seed(run)
    read(run, "TP-1", "2023-05-02", "-905")
    read(run, "TP-1", "2024-05-02", "-905")
    read(run, "TP-2", "2024-05-02", "-905")
    result = run("report", "history", "--line", "AL-2")
    assert "1 posts held their side" in result.output
    assert "1 only in 2024" in result.output


def test_a_stable_line_reports_nothing_on_either_table(
    run: Callable[..., Result],
) -> None:
    seed(run)
    read(run, "TP-1", "2023-05-02", "-905")
    read(run, "TP-1", "2024-05-02", "-910")
    result = run("report", "history", "--line", "AL-2")
    assert result.output.count("none") >= 2


def test_the_stations_are_printed_in_the_line_convention(
    run: Callable[..., Result],
) -> None:
    seed(run)
    read(run, "TP-1", "2023-05-02", "-905")
    read(run, "TP-1", "2024-05-02", "-800")
    assert "10+00.00" in run("report", "history", "--line", "AL-2").output


def test_a_line_that_is_not_there_exits_three(run: Callable[..., Result]) -> None:
    assert run("report", "history", "--line", "ZZ-9").exit_code == 3
