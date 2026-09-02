import logging
import sys
from enum import StrEnum
from typing import Final


class ColorFormatter(logging.Formatter):
    """Formatter applying ANSI color codes based on standard log levels."""

    class LogFormat(StrEnum):
        START = "\033["
        START_END = "m"
        END = "\033[0m"
        BOLD = "1"

        # Colors
        LIGHT_GRAY = "37"
        BLUE = "34"
        YELLOW = "93"
        RED = "91"

    COLOR_MAP: Final[dict[int, LogFormat]] = {
        logging.DEBUG: LogFormat.LIGHT_GRAY,
        logging.INFO: LogFormat.BLUE,
        logging.WARNING: LogFormat.YELLOW,
        logging.ERROR: LogFormat.RED,
        logging.CRITICAL: LogFormat.RED,
    }

    LEVEL_ALIASES: Final[dict[str, str]] = {
        "WARNING": "WARN",
        "CRITICAL": "FATAL",
    }

    use_color: bool

    def __init__(self, *args, use_color: bool | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        self.use_color = use_color if use_color is not None else sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        raw_level = self.LEVEL_ALIASES.get(record.levelname, record.levelname)
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        header = f"{timestamp} [{raw_level:<7}] {record.name}:"

        if self.use_color:
            color = self.COLOR_MAP.get(
                record.levelno, ColorFormatter.LogFormat.LIGHT_GRAY
            )
            header = (
                f"{ColorFormatter.LogFormat.START}{ColorFormatter.LogFormat.BOLD};{color}"
                f"{ColorFormatter.LogFormat.START_END}{header}{ColorFormatter.LogFormat.END}"
            )

        formatted_record = f"{header} {record.getMessage()}"

        if record.exc_info:
            if not formatted_record.endswith("\n"):
                formatted_record += "\n"
            formatted_record += self.formatException(record.exc_info)

        return formatted_record
