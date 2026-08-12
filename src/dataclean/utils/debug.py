from logging import Logger
from typing import Any

from dataclean.types import checked


@checked
def _log_args(logger: Logger, level: str = "DEBUG", **kwargs: Any) -> None:

    log_func = getattr(logger, level.lower(), None)
    if log_func is None:
        raise ValueError(f"Invalid log level: {level}")

    log_func("Arguments:")
    for key, value in kwargs.items():
        log_func("\t%s: %s", key, value)
