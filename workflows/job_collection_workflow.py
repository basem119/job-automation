from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings
from core.exceptions import ApplicationError
from core.logging import configure_logging
from core.version import version
from infrastructure.collectors.collector import Collector, CollectorRegistry
from infrastructure.greenhouse.collector import GreenhouseCollector
from infrastructure.remoteok.collector import RemoteOkCollector
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class JobCollectionWorkflow:
    """End-to-end workflow for collecting and storing jobs from multiple sources."""

    def __init__(
        self,
        collector: Collector | None = None,
        collectors: list[Collector] | None = None,
        repository: JobRepository | None = None,
        database: SQLiteDatabase | None = None,
    ) -> None:
        if collectors is None and collector is not None:
            collectors = [collector]
        self.collectors = collectors or []
        settings = Settings.load()
        self.database = database or SQLiteDatabase(settings.database_path)
        self.repository = repository or JobRepository(self.database)

    def run(self) -> dict[str, object]:
        started_at = time.perf_counter()
        logger.info("Downloading jobs")

        all_jobs: list = []
        collector_stats: list[dict[str, int | str]] = []
        total_downloaded = 0
        total_inserted = 0
        total_duplicates = 0

        for collector in self.collectors:
            collector_name = getattr(collector, "name", collector.__class__.__name__)
            try:
                jobs = collector.collect()
            except Exception as exc:
                logger.warning("Collector %s failed: %s", collector_name, exc)
                collector_stats.append(
                    {
                        "name": collector_name,
                        "downloaded": 0,
                        "inserted": 0,
                        "duplicates": 0,
                    }
                )
                continue

            logger.info("Collector: %s", collector_name)
            logger.info("Downloaded: %s", len(jobs))
            summary = self.repository.insert_jobs(jobs)
            logger.info("Inserted: %s", summary["inserted"])
            logger.info("Duplicates: %s", summary["duplicates"])

            collector_stats.append(
                {
                    "name": collector_name,
                    "downloaded": len(jobs),
                    "inserted": summary["inserted"],
                    "duplicates": summary["duplicates"],
                }
            )
            all_jobs.extend(jobs)
            total_downloaded += len(jobs)
            total_inserted += summary["inserted"]
            total_duplicates += summary["duplicates"]

        elapsed = time.perf_counter() - started_at
        logger.info("Overall: Total Downloaded %s", total_downloaded)
        logger.info("Overall: Total Inserted %s", total_inserted)
        logger.info("Overall: Total Duplicates %s", total_duplicates)
        logger.info("Execution Time: %.2f seconds", elapsed)

        return {
            "downloaded": total_downloaded,
            "inserted": total_inserted,
            "duplicates": total_duplicates,
            "total": total_inserted + total_duplicates,
            "collector_stats": collector_stats,
        }


def build_collectors(settings: Settings) -> list[Collector]:
    registry = CollectorRegistry()

    if settings.enable_remoteok:
        registry.register("remoteok", RemoteOkCollector())
    if settings.enable_greenhouse:
        registry.register("greenhouse", GreenhouseCollector())

    return registry.collectors


def main() -> int:
    settings = Settings.load()
    settings.validate_runtime_paths()
    configure_logging(settings.log_level, settings.log_directory)
    logger.info("Application version: %s", version)

    try:
        database = SQLiteDatabase(settings.database_path)
        collectors = build_collectors(settings)
        workflow = JobCollectionWorkflow(collectors=collectors, database=database)
        summary = workflow.run()

        logger.info("Jobs downloaded: %s", summary["downloaded"])
        logger.info("Jobs inserted: %s", summary["inserted"])
        logger.info("Jobs skipped (duplicates): %s", summary["duplicates"])
        return 0
    except (ApplicationError, ValueError) as exc:
        logger.error("Application startup failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
