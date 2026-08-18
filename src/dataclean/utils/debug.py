import logging
from logging import Logger
from typing import Any

from dataclean.types import checked


@checked
def _log_args(logger: Logger, level: int = logging.DEBUG, **kwargs: Any) -> None:

    if not logger.isEnabledFor(level):
        return

    log_func = getattr(logger, logging.getLevelName(level).lower(), None)
    if log_func is None:
        raise ValueError(f"Invalid log level: {level}")

    log_func("Arguments:")
    for key, value in kwargs.items():
        log_func("\t%s: %s", key, value)
