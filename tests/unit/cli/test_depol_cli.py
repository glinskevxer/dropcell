from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
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

HEADER = "Test Post,Off,Depolarised,Remark\n"
GOOD = HEADER + "TP-1,-905,-780,\nTP-2,-900,-880,\nTP-3,-910,,gate locked\n"

OFF_AT = "2025-03-14T06:00"
READ_AT = "2025-03-15T06:00"


@pytest.fixture
def depol_file(tmp_path: Path) -> Callable[[str], Path]:
    counter = {"n": 0}

    def write(text: str) -> Path:
        counter["n"] += 1
        target = tmp_path / f"depol-{counter['n']}.csv"
        target.write_text(text, encoding="utf-8")
        return target

    return write


def test_a_survey_is_loaded_and_scored(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    result = run(
        "survey",
        "depol",
        str(depol_file(GOOD)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert result.exit_code == 0
    assert "3 posts" in result.output
    assert "24.0 hours off" in result.output
    assert "1 of 2 posts read twice reached 100 mV" in result.output


def test_the_post_that_was_missed_is_reported(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    result = run(
        "survey",
        "depol",
        str(depol_file(GOOD)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert "1 posts were not read on the second pass" in result.output


def test_a_short_survey_says_it_is_not_decay(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    result = run(
        "survey",
        "depol",
        str(depol_file(GOOD)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        "2025-03-14T06:30",
    )
    assert "not long enough to be decay" in result.output


def test_a_full_survey_with_everybody_read_has_no_problems(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = HEADER + "TP-1,-905,-780,\nTP-2,-900,-770,\n"
    result = run(
        "survey",
        "depol",
        str(depol_file(text)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert "2 of 2 posts read twice" in result.output
    assert "not read on the second pass" not in result.output


def test_a_file_reading_one_post_twice_is_refused(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    text = HEADER + "TP-1,-905,-780,\nTP-1,-900,-770,\n"
    result = run(
        "survey",
        "depol",
        str(depol_file(text)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert result.exit_code == 2
    assert "reads one post twice" in result.output


def test_an_empty_file_is_refused(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    result = run(
        "survey",
        "depol",
        str(depol_file(HEADER)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert result.exit_code == 2


def test_two_surveys_against_one_switch_off_are_a_conflict(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    run(
        "survey",
        "depol",
        str(depol_file(GOOD)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    again = run(
        "survey",
        "depol",
        str(depol_file(GOOD + "TP-4,-905,-780,\n")),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert again.exit_code == 4


def test_the_decay_criterion_comes_from_the_settings(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    run(*ADD_LINE)
    result = run(
        "survey",
        "depol",
        str(depol_file(GOOD)),
        "--line",
        "AL-2",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert "reached 100 mV" in result.output


def test_a_line_that_is_not_there_exits_three(
    run: Callable[..., Result], depol_file: Callable[[str], Path]
) -> None:
    result = run(
        "survey",
        "depol",
        str(depol_file(GOOD)),
        "--line",
        "ZZ-9",
        "--off-at",
        OFF_AT,
        "--read-at",
        READ_AT,
    )
    assert result.exit_code == 3
