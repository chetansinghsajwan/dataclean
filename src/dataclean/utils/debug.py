"""Debug helper for logging function call arguments."""

import logging
from logging import Logger
from typing import Any

from dataclean.types import checked


@checked
def _log_args(logger: Logger, level: int = logging.DEBUG, **kwargs: Any) -> None:
    """Log each keyword argument as a separate line, if ``level`` is enabled.

    Does nothing if ``logger`` is not enabled for ``level``, avoiding the
    cost of formatting arguments that would not be logged anyway.

    Args:
        logger: Logger to write to.
        level: Logging level to log at. Defaults to ``logging.DEBUG``.
        **kwargs: Argument name/value pairs to log, one per line.

    Raises:
        ValueError: If ``level`` does not correspond to a known logging
            level name.
    """

    if not logger.isEnabledFor(level):
        return

    log_func = getattr(logger, logging.getLevelName(level).lower(), None)
    if log_func is None:
        raise ValueError(f"Invalid log level: {level}")

    log_func("Arguments:")
    for key, value in kwargs.items():
        log_func("\t%s: %s", key, value)
