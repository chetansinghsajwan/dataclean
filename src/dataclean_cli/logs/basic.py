import logging
import sys
from typing import Literal

from .color_formatter import ColorFormatter

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
