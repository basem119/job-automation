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
from infrastructure.sqlite.database import SQLiteDatabase
from utils.filesystem import validate_required_directories
from workflows.job_collection_workflow import JobCollectionWorkflow, build_collectors


def main() -> int:
    try:
        settings = Settings.load()
        logger = configure_logging(settings.log_level)

        logger.info("Application version: %s", version)
        logger.info("Configuration loaded")
        logger.info("Logging initialized")

        validate_required_directories()
        logger.info("Filesystem validated")

        database = SQLiteDatabase(settings.database_path)
        workflow = JobCollectionWorkflow(collectors=build_collectors(settings), database=database)
        summary = workflow.run()

        logger.info("Jobs downloaded: %s", summary["downloaded"])
        logger.info("Jobs inserted: %s", summary["inserted"])
        logger.info("Jobs skipped (duplicates): %s", summary["duplicates"])
        logger.info("Application initialized successfully")
        logger.info("Application finished")
        return 0
    except (ApplicationError, ConfigurationError, ValueError) as exc:
        logging.getLogger("job_automation").error("Application startup failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
