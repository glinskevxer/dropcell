"""What the build and the pipeline agree on, held in one place.

Every one of these has been wrong at some point in a way nothing else caught:
a pinned tool in the workflow that had moved on in the project file, a script
entry point naming a module that had been renamed, a coverage gate nobody had
noticed was switched off.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def project() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workflow() -> str:
    return (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_the_package_declares_the_python_it_needs(project: dict[str, Any]) -> None:
    assert project["project"]["requires-python"] == ">=3.12"


def test_every_runtime_dependency_is_pinned(project: dict[str, Any]) -> None:
    for requirement in project["project"]["dependencies"]:
        assert "==" in requirement, requirement


def test_every_development_dependency_is_pinned(project: dict[str, Any]) -> None:
    for requirement in project["project"]["optional-dependencies"]["dev"]:
        assert "==" in requirement, requirement


def test_the_build_backend_is_pinned_too(project: dict[str, Any]) -> None:
    assert project["build-system"]["requires"] == ["hatchling==1.27.0"]


def test_the_workflow_builds_with_the_same_backend(
    project: dict[str, Any],
    workflow: str,
) -> None:
    pinned = project["build-system"]["requires"][0]
    assert pinned in workflow


def test_the_script_entry_point_resolves(project: dict[str, Any]) -> None:
    import importlib

    target = project["project"]["scripts"]["dropcell"]
    module_name, _, attribute = target.partition(":")
    module = importlib.import_module(module_name)
    assert callable(getattr(module, attribute))


def test_the_coverage_gate_is_on(project: dict[str, Any]) -> None:
    assert project["tool"]["coverage"]["report"]["fail_under"] >= 90


def test_coverage_measures_branches(project: dict[str, Any]) -> None:
    assert project["tool"]["coverage"]["run"]["branch"] is True


def test_the_workflow_runs_everything_the_makefile_does(workflow: str) -> None:
    for step in ("ruff check", "ruff format", "mypy", "pytest", "check_migrations"):
        assert step in workflow


def test_the_workflow_installs_the_wheel_on_its_own(workflow: str) -> None:
    assert "python -m build --wheel" in workflow
    assert "pip install dist/*.whl" in workflow


def test_the_smoke_job_actually_uses_the_command(workflow: str) -> None:
    assert "dropcell init" in workflow
    assert "dropcell report protection" in workflow
    assert "dropcell register check" in workflow


def test_the_test_class_pattern_keeps_the_domain_records_out(
    project: dict[str, Any],
) -> None:
    assert project["tool"]["pytest"]["ini_options"]["python_classes"] == ["Case*"]


def test_mypy_is_strict(project: dict[str, Any]) -> None:
    assert project["tool"]["mypy"]["strict"] is True
    assert project["tool"]["mypy"]["warn_unreachable"] is True
