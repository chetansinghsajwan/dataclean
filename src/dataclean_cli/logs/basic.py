"""Level names and root logger setup for the command line tool."""

import logging
import sys
from typing import Literal

from .color_formatter import ColorFormatter

# Level names accepted on the command line, mapped to the logging constants.
levels = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

levelNames = set(levels.keys())
LevelNames = Literal["debug", "info", "warn", "error", "critical"]

defaultLevel = "debug"


def setup_logging(level: str | int | None = None) -> None:
    """Send root logger output to stdout in colour at the given level (debug when unset)."""
    if level is None:
        log_level = logging.DEBUG
    else:
        log_level = levels[level.lower()] if isinstance(level, str) else level

    logger = logging.getLogger()
    logger.setLevel(log_level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)

    formatter = ColorFormatter(use_color=True)
    stream_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
