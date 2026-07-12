from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings
from core.exceptions import ApplicationError, ConfigurationError
from core.logging import configure_logging
from core.version import version
from utils.filesystem import validate_required_directories


def main() -> int:
    try:
        settings = Settings.load()
        logger = configure_logging(settings.log_level)

        logger.info("Application version: %s", version)
        logger.info("Configuration loaded")
        logger.info("Logging initialized")

        validate_required_directories()
        logger.info("Filesystem validated")

        logger.info("Application initialized successfully")
        logger.info("Application finished")
        return 0
    except (ApplicationError, ConfigurationError, ValueError) as exc:
        logging.getLogger("job_automation").error("Application startup failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
