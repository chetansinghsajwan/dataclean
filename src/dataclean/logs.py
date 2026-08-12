import logging
import sys
from enum import StrEnum

from dataclean.config import config


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        fmt = (
            f"{color}%(asctime)s | %(levelname)-8s | %(name)s | %(message)s{self.RESET}"
        )
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def default_logger_provider(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorFormatter())
    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:

    if config.logger_provider is not None:
        logger = config.logger_provider(name)
    else:
        logger = default_logger_provider(name)

    logger.setLevel(config.log_level)

    if config.log_format is not None:
        formatter = logging.Formatter(config.log_format)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    if config.log_handlers is not None:
        for handler in config.log_handlers:
            logger.addHandler(handler)

    return logger
