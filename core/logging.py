from __future__ import annotations

import logging
from typing import Final

from core.exceptions import ConfigurationError

DEFAULT_LOG_LEVEL: Final[str] = "INFO"
VALID_LOG_LEVELS: Final[set[str]] = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


def configure_logging(log_level: str = DEFAULT_LOG_LEVEL) -> logging.Logger:
    """Configure the root logger for the application."""
    level_name = (log_level or DEFAULT_LOG_LEVEL).strip().upper()
    if level_name not in VALID_LOG_LEVELS:
        raise ConfigurationError(f"Unsupported LOG_LEVEL: {log_level}")

    logging.basicConfig(
        level=getattr(logging, level_name),
        format="%(asctime)s | %(levelname)s | %(module)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    return logging.getLogger("job_automation")
