from __future__ import annotations

import logging
import sys

import pytest

from dropcell import logs


@pytest.fixture
def captured(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Wire pytest's capture onto the package logger.

    The package logger does not propagate, on purpose, so nothing it emits
    reaches the root logger that pytest normally listens on. That is the
    behaviour under test as much as anything else here, so the capture handler
    is attached to the package logger directly rather than the setting relaxed.
    """
    logger = logs.configure(2)
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger=logs.LOGGER_NAME)
    return caplog


def test_no_flags_means_warnings_and_above() -> None:
    assert logs.level_for(0) == logging.WARNING


def test_one_flag_means_the_useful_lines() -> None:
    assert logs.level_for(1) == logging.INFO


def test_two_flags_mean_everything() -> None:
    assert logs.level_for(2) == logging.DEBUG
    assert logs.level_for(9) == logging.DEBUG


def test_a_negative_count_is_treated_as_none() -> None:
    assert logs.level_for(-1) == logging.WARNING


def test_configuring_puts_one_stream_handler_on_standard_error() -> None:
    logger = logs.configure(1)
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr
    assert logger.level == logging.INFO


def test_configuring_twice_does_not_stack_handlers() -> None:
    logs.configure(1)
    logger = logs.configure(1)
    assert len(logger.handlers) == 1


def test_quiet_silences_everything_below_critical() -> None:
    logger = logs.configure(2, quiet=True)
    assert logger.level == logging.CRITICAL


def test_nothing_propagates_to_the_root_logger() -> None:
    assert logs.configure(1).propagate is False


def test_a_named_logger_sits_under_the_package() -> None:
    assert logs.get("store").name == "dropcell.store"
    assert logs.get().name == "dropcell"


def test_opening_a_register_is_logged(captured: pytest.LogCaptureFixture) -> None:
    logs.opened("cp.sqlite", version=13)
    assert "opened cp.sqlite at schema version 13" in captured.text


def test_migrations_are_logged_with_their_versions(
    captured: pytest.LogCaptureFixture,
) -> None:
    logs.migrated("cp.sqlite", [1, 2, 3])
    assert "applied 1, 2, 3" in captured.text


def test_no_migrations_logs_nothing(captured: pytest.LogCaptureFixture) -> None:
    logs.migrated("cp.sqlite", [])
    assert captured.text == ""


def test_an_import_is_logged_with_its_counts(
    captured: pytest.LogCaptureFixture,
) -> None:
    logs.imported("annual.csv", kind="annual", accepted=40, rejected=2, written=38)
    assert "loaded annual.csv as annual, 40 rows read, 2 held" in captured.text
    assert "written=38" in captured.text


def test_an_unnamed_input_is_still_logged(captured: pytest.LogCaptureFixture) -> None:
    logs.imported("", kind="cis", accepted=1, rejected=0)
    assert "loaded the input as cis" in captured.text


def test_a_refusal_is_a_warning_rather_than_an_error(
    captured: pytest.LogCaptureFixture,
) -> None:
    logs.refused("annual.csv", "loaded before")
    assert "refused annual.csv, loaded before" in captured.text
    assert captured.records[-1].levelno == logging.WARNING
