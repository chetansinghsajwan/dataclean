import logging
import sys

from .color_formatter import ColorFormatter


def default_logger_provider(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorFormatter())
    logger.addHandler(handler)

    return logger
