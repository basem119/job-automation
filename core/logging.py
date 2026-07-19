from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from core.exceptions import ConfigurationError
from utils.filesystem import ensure_directory

DEFAULT_LOG_LEVEL: Final[str] = "INFO"
VALID_LOG_LEVELS: Final[set[str]] = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


def configure_logging(
    log_level: str = DEFAULT_LOG_LEVEL,
    log_directory: Path | str | None = None,
) -> logging.Logger:
    """Configure the root logger for the application."""
    level_name = (log_level or DEFAULT_LOG_LEVEL).strip().upper()
    if level_name not in VALID_LOG_LEVELS:
        raise ConfigurationError(f"Unsupported LOG_LEVEL: {log_level}")

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_directory is not None:
        directory = ensure_directory(Path(log_directory))
        handlers.append(logging.FileHandler(directory / "job-automation.log", encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level_name),
        format="%(asctime)s | %(levelname)s | %(module)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )

    return logging.getLogger("job_automation")
