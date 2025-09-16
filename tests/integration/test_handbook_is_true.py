"""Running what the handbook says, in the order it says to run it.

Documentation rots the moment it stops being executed. The handbook's first two
sections are a list of commands somebody is meant to type in order, and this
suite types them, in that order, against a real register.

It is not a test of the handbook's prose. It is a test that every command named
in it exists, takes the options it is shown taking, and does the thing the
section it is under says it does. A command renamed without the handbook being
updated fails here rather than in a depot.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dropcell.handbook import section
from tests.integration.conftest import Run

COMMAND = re.compile(r"^dropcell ([a-z-]+(?: [a-z-]+)?)")


def named_commands(key: str) -> list[str]:
    """Every command the handbook names in one section, in the order it names them."""
    found: list[str] = []
    for line in section(key).body.splitlines():
        match = COMMAND.match(line.strip())
        if match is None:
            continue
        words = match.group(1).split()
        found.append(" ".join(word for word in words if word not in {"FILE", "TAG"}))
    return found


def resolve(path: str) -> object:
    """The command object at the end of a path of words, or nothing."""
    import click

    from dropcell.cli.main import main

    command: object = main
    for word in path.split():
        if not isinstance(command, click.Group):
            return None
        command = command.commands.get(word)
        if command is None:
            return None
    return command


@pytest.mark.parametrize("key", ["start", "year"])
def test_the_section_names_some_commands(key: str) -> None:
    assert len(named_commands(key)) >= 5


@pytest.mark.parametrize("key", ["start", "year"])
def test_every_command_the_handbook_names_exists(key: str) -> None:
    for path in named_commands(key):
        assert resolve(path) is not None, path


def test_the_setting_up_section_runs_in_the_order_it_is_written(ok: Run) -> None:
    ok("init")
    ok(
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
    ok(
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
    ok(
        "post",
        "add",
        "TP-1",
        "--line",
        "AL-2",
        "--at",
        "10+00.00",
        "--installed",
        "1998-05-04",
        "--lead",
        "pipe",
    )
    ok(
        "rectifier",
        "add-bed",
        "GB-1",
        "--kind",
        "deep_well",
        "--material",
        "high_silicon_iron",
        "--anodes",
        "12",
        "--mass",
        "20 kg",
        "--installed",
        "2004-09-01",
        "--design-current",
        "15 A",
    )
    ok(
        "rectifier",
        "add",
        "RU-1",
        "--line",
        "AL-2",
        "--at",
        "12+00.00",
        "--bed",
        "GB-1",
        "--rated-volts",
        "24",
        "--rated-amps",
        "20",
        "--installed",
        "2004-09-01",
    )
    ok(
        "plant",
        "add-casing",
        "CS-1",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--installed",
        "1998-05-04",
    )
    assert ok("register", "check").exit_code == 0


def test_the_handbook_is_right_that_a_line_needs_segments(run: Run, ok: Run) -> None:
    ok("init")
    ok(
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
    failed = run("register", "check")
    assert failed.exit_code == 1
    assert "line has no segments" in failed.output


def test_the_year_section_runs_end_to_end(ok: Run, tmp_path: Path) -> None:
    ok("init")
    ok(
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
    ok(
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
    ok("post", "add", "TP-1", "--line", "AL-2", "--at", "10+00.00", "--installed", "1998-05-04")
    ok(
        "rectifier",
        "add-bed",
        "GB-1",
        "--kind",
        "deep_well",
        "--material",
        "high_silicon_iron",
        "--anodes",
        "12",
        "--mass",
        "20 kg",
        "--installed",
        "2004-09-01",
        "--design-current",
        "15 A",
    )
    ok(
        "rectifier",
        "add",
        "RU-1",
        "--line",
        "AL-2",
        "--at",
        "12+00.00",
        "--bed",
        "GB-1",
        "--rated-volts",
        "24",
        "--rated-amps",
        "20",
        "--installed",
        "2004-09-01",
    )

    survey = tmp_path / "annual.csv"
    survey.write_text("Test Post,Date,On,Off\nTP-1,2025-02-11,-1120,-905\n", encoding="utf-8")
    checked = ok("import", "check", str(survey))
    assert "best match is annual" in checked.output
    ok("import", "annual", str(survey))
    ok(
        "rectifier",
        "check",
        "RU-1",
        "--volts",
        "18.5",
        "--amps",
        "12.4",
        "--coarse",
        "3",
        "--fine",
        "2",
    )
    ok(
        "plant",
        "add-casing",
        "CS-1",
        "--line",
        "AL-2",
        "--at",
        "40+00.00",
        "--installed",
        "1998-05-04",
    )
    ok("plant", "test-casing", "CS-1", "--pipe-on", "-1120", "--casing-on", "-560")

    cis = tmp_path / "cis.csv"
    rows = "".join(
        f"{index // 20}+{(index % 20) * 5:05.2f},-1120,-905,\n" for index in range(40)
    )
    cis.write_text("Station,P/S On,P/S Off,Remark\n" + rows, encoding="utf-8")
    ok("survey", "cis", str(cis), "--line", "AL-2", "--date", "2025-03-01")

    dcvg = tmp_path / "dcvg.csv"
    dcvg.write_text(
        "Station,Date,Gradient,Total Shift\n150+00.00,2025-03-05,320,400\n",
        encoding="utf-8",
    )
    ok("survey", "dcvg", str(dcvg), "--line", "AL-2")

    assert "protection rate" in ok("report", "protection", "--line", "AL-2").output
    assert "Monitoring compliance" in ok("report", "compliance", "--line", "AL-2").output
    ok(
        "finding",
        "raise",
        "--line",
        "AL-2",
        "--kind",
        "coating_defect",
        "--from",
        "150+00.00",
        "--summary",
        "category four at the beck crossing",
    )
    ok("finding", "clear", "F-2025-001", "--by", "R Ellis")
    assert "annual report" in ok("report", "annual", "--line", "AL-2").output


def test_the_handbook_can_be_printed_section_by_section(ok: Run) -> None:
    for key in ("start", "year", "reading", "groups", "units", "exits"):
        assert ok("handbook", key).output.strip()
