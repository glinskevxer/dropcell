"""Logging, and the two things it must not do.

It must not print to standard output. Half these commands are piped into a file
or into another program, and a log line in the middle of a CSV export is a
corrupt export. Everything goes to standard error.

And it must not be on by default. A field engineer running one command wants one
answer, and a tool that prefaces it with six lines about opening a connection is
a tool people write a wrapper script to silence. The default is warnings and
above, which in a working run is nothing at all.

What is worth logging is narrow: the register that was opened, every migration
that ran, every file that was loaded and what it did. Those are the four
questions asked when somebody wants to know why the register says what it says,
and none of them can be answered from the register itself.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

LOGGER_NAME = "dropcell"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

LEVELS: dict[int, int] = {
    0: logging.WARNING,
    1: logging.INFO,
    2: logging.DEBUG,
}


def level_for(verbosity: int) -> int:
    """The logging level a count of verbose flags asks for."""
    if verbosity < 0:
        return logging.WARNING
    return LEVELS.get(verbosity, logging.DEBUG)


def configure(verbosity: int = 0, *, quiet: bool = False) -> logging.Logger:
    """Set logging up once, on standard error, and hand back the root logger."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT, datefmt=TIME_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.CRITICAL if quiet else level_for(verbosity))
    logger.propagate = False
    return logger


def get(name: str = "") -> logging.Logger:
    """A logger under the package's own name."""
    return logging.getLogger(LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}")


def opened(path: str, *, version: int) -> None:
    """Note that a register was opened and at what schema version."""
    get("store").info("opened %s at schema version %d", path, version)


def migrated(path: str, versions: list[int]) -> None:
    """Note every migration that ran."""
    if not versions:
        return
    get("store").info(
        "migrated %s, applied %s", path, ", ".join(str(item) for item in versions)
    )


def imported(source: str, *, kind: str, accepted: int, rejected: int, **detail: Any) -> None:
    """Note a file that was loaded and what became of its rows."""
    extra = "".join(f" {name}={value}" for name, value in sorted(detail.items()))
    get("ingest").info(
        "loaded %s as %s, %d rows read, %d held%s",
        source or "the input",
        kind,
        accepted,
        rejected,
        extra,
    )


def refused(source: str, reason: str) -> None:
    """Note a file that was refused, which is a warning rather than an error."""
    get("ingest").warning("refused %s, %s", source or "the input", reason)
