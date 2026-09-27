import logging
import sys
from typing import Any

from app.config import settings


def setup_logging() -> logging.Logger:
    """Configure structured console logging for the application."""
    logger = logging.getLogger("eve_healthcare")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
