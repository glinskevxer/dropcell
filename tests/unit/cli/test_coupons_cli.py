from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
    "--soil",
    "2500 ohm-cm",
)


def seed(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post",
        "add",
        "TP-114",
        "--line",
        "AL-2",
        "--at",
        "12+45.50",
        "--installed",
        "1998-05-04",
        "--lead",
        "pipe",
        "--lead",
        "coupon",
    )
    run(
        "coupon",
        "add",
        "CP-4",
        "--post",
        "TP-114",
        "--shunt",
        "0.01",
        "--installed",
        "2019-06-03",
    )


def test_a_coupon_can_be_added(run: Callable[..., Result]) -> None:
    seed(run)
    listed = run("coupon", "status", "--line", "AL-2")
    assert "CP-4" in listed.output


def test_a_side_coupon_says_it_is_not_the_pessimistic_case(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post",
        "add",
        "TP-114",
        "--line",
        "AL-2",
        "--at",
        "12+45.50",
        "--installed",
        "1998-05-04",
        "--lead",
        "coupon",
    )
    added = run(
        "coupon",
        "add",
        "CP-4",
        "--post",
        "TP-114",
        "--shunt",
        "0.01",
        "--installed",
        "2019-06-03",
    )
    assert "not the pessimistic case" in added.output


def test_a_bottom_coupon_says_nothing_extra(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    run(*ADD_SEGMENT)
    run(
        "post",
        "add",
        "TP-114",
        "--line",
        "AL-2",
        "--at",
        "12+45.50",
        "--installed",
        "1998-05-04",
        "--lead",
        "coupon",
    )
    added = run(
        "coupon",
        "add",
        "CP-4",
        "--post",
        "TP-114",
        "--shunt",
        "0.01",
        "--installed",
        "2019-06-03",
        "--facing",
        "bottom",
    )
    assert "pessimistic" not in added.output


def test_a_coupon_on_a_post_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    run(*ADD_LINE)
    result = run(
        "coupon",
        "add",
        "CP-4",
        "--post",
        "TP-999",
        "--shunt",
        "0.01",
        "--installed",
        "2019-06-03",
    )
    assert result.exit_code == 3


def test_a_coupon_never_read_says_so(run: Callable[..., Result]) -> None:
    seed(run)
    assert "never or off segment" in run("coupon", "status", "--line", "AL-2").output


def test_a_reading_shows_up_in_the_status(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "coupon",
        "read",
        "CP-4",
        "--on",
        "-1120",
        "--disconnected",
        "-905",
        "--dc-shunt",
        "0.001",
        "--ac-shunt",
        "0.01",
    )
    status = run("coupon", "status", "--line", "AL-2")
    assert "-905" in status.output
    assert "2025-03-14" in status.output


def test_a_coupon_taking_too_much_ac_is_flagged_as_hidden(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run(
        "coupon",
        "read",
        "CP-4",
        "--on",
        "-1120",
        "--disconnected",
        "-905",
        "--ac-shunt",
        "0.15",
    )
    status = run("coupon", "status", "--line", "AL-2")
    assert "Potential hides it" in status.output
    assert "yes" in status.output


def test_a_quiet_coupon_is_not_flagged(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "coupon",
        "read",
        "CP-4",
        "--on",
        "-1120",
        "--disconnected",
        "-905",
        "--ac-shunt",
        "0.0001",
    )
    status = run("coupon", "status", "--line", "AL-2")
    rows = [line for line in status.output.splitlines() if "CP-4" in line]
    assert rows and not rows[0].rstrip().endswith("yes")


def test_reading_a_coupon_that_is_not_there_exits_three(
    run: Callable[..., Result],
) -> None:
    assert run("coupon", "read", "CP-9", "--on", "-1120").exit_code == 3


def test_a_second_reading_on_the_same_day_is_a_conflict(
    run: Callable[..., Result],
) -> None:
    seed(run)
    run("coupon", "read", "CP-4", "--on", "-1120")
    assert run("coupon", "read", "CP-4", "--on", "-1100").exit_code == 4


def test_a_coupon_file_can_be_imported(run: Callable[..., Result], tmp_path: Path) -> None:
    seed(run)
    target = tmp_path / "coupons.csv"
    target.write_text(
        "Coupon,Date,On,Disconnected,DC Shunt,AC Shunt\n"
        "CP-4,2025-03-14,-1120,-905,0.001,0.01\n",
        encoding="utf-8",
    )
    result = run("coupon", "import", str(target))
    assert "1 readings written" in result.output


def test_a_thin_row_is_named_on_import(run: Callable[..., Result], tmp_path: Path) -> None:
    seed(run)
    target = tmp_path / "coupons.csv"
    target.write_text("Coupon,Date,On\nCP-4,2025-03-14,-1120\n", encoding="utf-8")
    result = run("coupon", "import", str(target))
    assert "nothing but a connected potential" in result.output


def test_a_line_with_no_coupons_says_so(run: Callable[..., Result]) -> None:
    run(*ADD_LINE)
    assert "no coupons on this line" in run("coupon", "status", "--line", "AL-2").output
