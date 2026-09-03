import logging

import ibis


def setup_logging() -> None:

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
            fmt = f"{color}%(asctime)s | %(levelname)-8s | %(name)s | %(message)s{self.RESET}"
            formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
            return formatter.format(record)

    logger = logging.getLogger("dataclean")
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logger.addHandler(handler)


setup_logging()

ibis.Table
