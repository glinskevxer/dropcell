from __future__ import annotations

import json
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
    run("post", "read", "TP-1", "--on", "-1120", "--off", "-905")


def test_the_protection_report_emits_readable_json(run: Callable[..., Result]) -> None:
    seed(run)
    result = run("report", "protection", "--line", "AL-2", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["line_code"] == "AL-2"
    assert payload["posts"] == 2
    assert payload["judged"] == 1
    assert payload["protection_rate"] == 1.0


def test_a_post_nobody_read_carries_nulls_rather_than_zeros(
    run: Callable[..., Result],
) -> None:
    seed(run)
    payload = json.loads(run("report", "protection", "--line", "AL-2", "--json").output)
    rows = {row["post"]: row for row in payload["rows"]}
    assert rows["TP-2"]["off_mv"] is None
    assert rows["TP-2"]["read_on"] is None
    assert rows["TP-2"]["assessed"] is False


def test_nothing_is_rounded_in_the_json(run: Callable[..., Result]) -> None:
    seed(run)
    payload = json.loads(run("report", "protection", "--line", "AL-2", "--json").output)
    rows = {row["post"]: row for row in payload["rows"]}
    assert rows["TP-1"]["station_m"] == 1000 * 0.3048


def test_the_criteria_met_are_named(run: Callable[..., Result]) -> None:
    seed(run)
    payload = json.loads(run("report", "protection", "--line", "AL-2", "--json").output)
    rows = {row["post"]: row for row in payload["rows"]}
    assert rows["TP-1"]["met"] == ["polarised_potential"]
    assert rows["TP-1"]["exceeded"] == []


def test_the_exception_register_emits_json(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--to",
        "12+00.00",
        "--summary",
        "under criterion",
    )
    payload = json.loads(run("report", "exceptions", "--json").output)
    assert payload[0]["code"] == "F-2025-001"
    assert payload[0]["due_by"] is None
    assert payload[0]["length_m"] > 0


def test_the_compliance_register_emits_json(run: Callable[..., Result]) -> None:
    seed(run)
    payload = json.loads(run("report", "compliance", "--line", "AL-2", "--json").output)
    assert payload["pairs"] == 2
    codes = {row["asset"] for row in payload["rows"]}
    assert codes == {"TP-1", "TP-2"}


def test_a_compliance_row_carries_its_visits_and_reasons(
    run: Callable[..., Result],
) -> None:
    seed(run)
    payload = json.loads(run("report", "compliance", "--line", "AL-2", "--json").output)
    rows = {row["asset"]: row for row in payload["rows"]}
    assert rows["TP-1"]["visits"] == ["2025-03-14"]
    assert isinstance(rows["TP-2"]["reasons"], list)


def test_the_ageing_table_emits_json(run: Callable[..., Result]) -> None:
    seed(run)
    run(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "under_criterion",
        "--from",
        "10+00.00",
        "--summary",
        "under criterion",
    )
    payload = json.loads(run("report", "ageing", "--json").output)
    assert payload["rows"][0]["kind"] == "under_criterion"
    assert payload["rows"][0]["total"] == 1
    assert len(payload["rows"][0]["buckets"]) == 5


def test_an_empty_register_still_emits_valid_json(run: Callable[..., Result]) -> None:
    assert json.loads(run("report", "exceptions", "--json").output) == []
    payload = json.loads(run("report", "ageing", "--json").output)
    assert payload["rows"] == []


def test_the_json_is_sorted_so_a_diff_is_readable(run: Callable[..., Result]) -> None:
    seed(run)
    text = run("report", "protection", "--line", "AL-2", "--json").output
    keys = [line.strip().split('"')[1] for line in text.splitlines() if line.startswith('  "')]
    assert keys == sorted(keys)
