from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings
from core.logging import configure_logging
from core.version import version
from infrastructure.remoteok.collector import RemoteOkCollector
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class JobCollectionWorkflow:
    """End-to-end workflow for collecting and storing RemoteOK jobs."""

    def __init__(
        self,
        collector: RemoteOkCollector | None = None,
        repository: JobRepository | None = None,
        database: SQLiteDatabase | None = None,
    ) -> None:
        self.collector = collector or RemoteOkCollector()
        self.database = database or SQLiteDatabase()
        self.repository = repository or JobRepository(self.database)

    def run(self) -> dict[str, int]:
        started_at = time.perf_counter()
        logger.info("Downloading jobs")

        jobs = self.collector.collect()
        logger.info("Jobs parsed: %s", len(jobs))
        logger.info("Jobs downloaded: %s", len(jobs))

        summary = self.repository.insert_jobs(jobs)
        logger.info("Jobs inserted: %s", summary["inserted"])
        logger.info("Jobs skipped (duplicates): %s", summary["duplicates"])

        elapsed = time.perf_counter() - started_at
        logger.info("Total execution time: %.2f seconds", elapsed)

        return {
            "downloaded": len(jobs),
            "inserted": summary["inserted"],
            "duplicates": summary["duplicates"],
            "total": summary["total"],
        }


def main() -> int:
    settings = Settings.load()
    configure_logging(settings.log_level)
    logger.info("Application version: %s", version)

    database = SQLiteDatabase(settings.database_path)
    workflow = JobCollectionWorkflow(database=database)
    summary = workflow.run()

    logger.info("Jobs downloaded: %s", summary["downloaded"])
    logger.info("Jobs inserted: %s", summary["inserted"])
    logger.info("Jobs skipped (duplicates): %s", summary["duplicates"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
