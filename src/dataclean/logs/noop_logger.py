import logging
from typing import Any


class NoopLogger(logging.Logger):
    """A strict subclass of logging.Logger that completely silences all operations.

    By short-circuiting the main internal entry points (`_log`, `handle`, and
    `log`), this class safely suppresses all convenience methods, level-checking
    gates, and structural log recording without triggering side-effects or leaks.
    """

    def __init__(self, name: str = "noop_logger") -> None:
        # Shallow inline allocation to avoid heavy thread synchronization structures
        self.name = name
        self.disabled = True
        self.filters = []
        self.handlers = []
        self.level = logging.CRITICAL
        self.propagate = False

    # -------------------------------------------------------------------------
    # Core Internal Chokepoints (Catches all default formatting & dispatching)
    # -------------------------------------------------------------------------

    def _log(
        self,
        level: int,
        msg: Any,
        args: Any,
        exc_info: Any = None,
        extra: Any = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None:
        """Short-circuits convenience methods (.info, .debug, .error, etc.)."""
        pass

    def handle(self, record: logging.LogRecord) -> None:
        """Short-circuits direct manual record submissions passed down the pipeline."""
        pass

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Guards explicit .log() calls from initiating baseline evaluations."""
        pass

    # -------------------------------------------------------------------------
    # Explicit Method Overrides (Guards individual user-facing convenience endpoints)
    # -------------------------------------------------------------------------

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    # Deprecated & Custom Level Aliases
    def warn(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    def fatal(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        pass

    # -------------------------------------------------------------------------
    # Level Evaluation Gates (Prevents redundant string interpolations upstream)
    # -------------------------------------------------------------------------

    def isEnabledFor(self, level: int) -> bool:
        """Forces all level threshold evaluation queries to fail instantly.

        This short-circuits loops like 'if logger.isEnabledFor(logging.DEBUG):'
        to skip execution entirely, minimizing pipeline processing overhead.
        """
        return False


# Global instance reference for the Shaw Gibbs platform layers fallback
noop_logger = NoopLogger()
