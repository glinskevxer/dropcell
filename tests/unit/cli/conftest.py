from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from dropcell.cli.main import main


@pytest.fixture
def register(tmp_path: Path) -> Path:
    return tmp_path / "cp.sqlite"


@pytest.fixture
def run(register: Path) -> Callable[..., Result]:
    runner = CliRunner()

    def invoke(*args: str, today: str = "2025-03-14", input_text: str | None = None) -> Result:
        argv: Sequence[str] = ["--register", str(register), "--today", today, *args]
        return runner.invoke(main, list(argv), input=input_text)

    return invoke
