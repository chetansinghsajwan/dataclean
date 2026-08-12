import logging
from enum import StrEnum

from dataclean.config import config


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def default_logger_provider(name: str) -> logging.Logger:
    return logging.getLogger(name)


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
