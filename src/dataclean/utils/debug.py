from logging import Logger
from typing import Any

from dataclean.logs import LogLevel
from dataclean.types import checked


@checked
def _log_args(logger: Logger, level: LogLevel = LogLevel.DEBUG, **kwargs: Any) -> None:

    if not logger.isEnabledFor(level.value):
        return

    log_func = getattr(logger, str(level).lower(), None)
    if log_func is None:
        raise ValueError(f"Invalid log level: {level}")

    log_func("Arguments:")
    for key, value in kwargs.items():
        log_func("\t%s: %s", key, value)
