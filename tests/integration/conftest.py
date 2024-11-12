"""Fixtures for the end to end suite.

These tests drive the command line the way somebody actually would, against a
real file on disk, in the order the work happens: build the register, put the
plant in it, load a survey, look at what came out, raise the findings, report.

Nothing here reaches into a repository. If a step cannot be done through the
command line then the command line has a hole in it, and finding those holes is
half of what this suite is for.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from dropcell.cli.main import main

Run = Callable[..., Result]


@pytest.fixture
def register(tmp_path: Path) -> Path:
    return tmp_path / "cp.sqlite"


@pytest.fixture
def run(register: Path) -> Run:
    runner = CliRunner()

    def invoke(*args: str, today: str = "2025-03-14") -> Result:
        argv: Sequence[str] = ["--register", str(register), "--today", today, *args]
        return runner.invoke(main, list(argv))

    return invoke


@pytest.fixture
def ok(run: Run) -> Run:
    def invoke(*args: str, today: str = "2025-03-14") -> Result:
        result = run(*args, today=today)
        assert result.exit_code == 0, f"{args} failed: {result.output}"
        return result

    return invoke


@pytest.fixture
def line_built(ok: Run) -> Run:
    """A register with one line, one segment, three posts and a rectifier."""
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
        "300+00.00",
        "--coating",
        "coal_tar",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1974",
        "--soil",
        "4500 ohm-cm",
    )
    ok(
        "segment",
        "add",
        "AL-2-002",
        "--line",
        "AL-2",
        "--from",
        "300+00.01",
        "--to",
        "600+00.00",
        "--coating",
        "tape_wrap",
        "--diameter",
        "323.9 mm",
        "--wall",
        "6.35 mm",
        "--installed",
        "1982",
        "--class-location",
        "3",
    )
    for code, station in (
        ("TP-101", "10+00.00"),
        ("TP-102", "150+00.00"),
        ("TP-103", "420+00.00"),
    ):
        ok("post", "add", code, "--line", "AL-2", "--at", station, "--installed", "1998-05-04")
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
    return ok
