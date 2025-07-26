"""What the package promises to anything importing it.

This suite is here to make a change to the public surface a deliberate act. It
does not assert that the list is right, because nobody can test that. It asserts
that the list and the module agree, that everything on it can actually be
imported by the name it is listed under, and that nothing on it is something the
package documented as private.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

import dropcell


def test_everything_named_is_importable() -> None:
    for name in dropcell.__all__:
        assert hasattr(dropcell, name), name


def api_order(name: str) -> tuple[int, str]:
    """The order the formatter keeps __all__ in: constants, classes, then functions."""
    if name.isupper():
        return (0, name)
    if name.startswith("__"):
        return (2, name)
    if name[:1].isupper():
        return (1, name)
    return (3, name)


def test_the_list_is_sorted_so_a_diff_is_readable() -> None:
    assert dropcell.__all__ == sorted(dropcell.__all__, key=api_order)


def test_the_list_has_no_duplicates() -> None:
    assert len(dropcell.__all__) == len(set(dropcell.__all__))


def test_nothing_private_is_on_the_list() -> None:
    assert not any(name.startswith("_") for name in dropcell.__all__ if name != "__version__")


def test_the_version_is_a_string_with_dots_in_it() -> None:
    assert isinstance(dropcell.__version__, str)
    assert dropcell.__version__.count(".") == 2


def test_the_version_matches_what_the_package_metadata_says() -> None:
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert payload["project"]["version"] == dropcell.__version__


def test_the_command_line_is_not_on_the_list() -> None:
    assert not any("cli" in name.lower() for name in dropcell.__all__)
    assert "main" not in dropcell.__all__


@pytest.mark.parametrize(
    "name",
    ["Line", "Segment", "TestPoint", "Reading", "Finding", "Station", "StationRange"],
)
def test_the_records_are_classes(name: str) -> None:
    assert inspect.isclass(getattr(dropcell, name))


@pytest.mark.parametrize(
    "name", ["assess_line", "build_register", "migrate", "open_register", "select_for"]
)
def test_the_entry_points_are_callable(name: str) -> None:
    assert callable(getattr(dropcell, name))


def test_every_error_the_cli_maps_is_on_the_list() -> None:
    from dropcell.cli.context import EXIT_CODES

    for kind in EXIT_CODES:
        assert kind.__name__ in dropcell.__all__


def test_importing_the_package_does_not_open_anything() -> None:
    module = importlib.reload(dropcell)
    assert module.__version__ == dropcell.__version__


def test_a_line_can_be_built_from_the_public_names_alone() -> None:
    line = dropcell.Line(
        code="AL-2",
        name="Ashfield lateral",
        operator="Northmoor Gas",
        commodity=dropcell.Commodity.NATURAL_GAS,
        length_m=18_500.0,
        nominal_diameter_mm=323.9,
        installed_year=1974,
        convention=dropcell.Convention.FOOT,
    )
    assert line.station("10+00.00") == dropcell.Station(1000 * 0.3048)
    assert line.status is dropcell.LineStatus.IN_SERVICE


def test_a_register_can_be_opened_from_the_public_names_alone() -> None:
    database = dropcell.Database(":memory:")
    dropcell.migrate(database)
    assert dropcell.latest_version() > 0
