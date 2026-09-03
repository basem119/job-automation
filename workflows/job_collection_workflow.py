from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings
from core.exceptions import ApplicationError, ConfigurationError
from core.logging import configure_logging
from core.version import version
from infrastructure.adzuna.client import AdzunaClient
from infrastructure.adzuna.collector import AdzunaCollector
from infrastructure.arbeitnow.collector import ArbeitnowCollector
from infrastructure.collectors.collector import CollectionResult, Collector, CollectorRegistry, DisabledCollector
from infrastructure.greenhouse.collector import GreenhouseCollector
from infrastructure.jobicy.collector import JobicyCollector
from infrastructure.remoteok.collector import RemoteOkCollector
from infrastructure.remotive.collector import RemotiveCollector
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
        total_failed_records = 0
        sources_attempted = 0
        sources_succeeded = 0
        sources_failed = 0

        for collector in self.collectors:
            collector_name = getattr(collector, "name", collector.__class__.__name__)
            collector_started_at = time.perf_counter()

            if not getattr(collector, "enabled", True):
                logger.info("Collector skipped (disabled): %s", collector_name)
                collector_stats.append(
                    {
                        "name": collector_name,
                        "status": "disabled",
                        "downloaded": 0,
                        "inserted": 0,
                        "duplicates": 0,
                        "failed": 0,
                    }
                )
                continue

            sources_attempted += 1

            try:
                collection_output = collector.collect()
                if isinstance(collection_output, CollectionResult):
                    jobs = collection_output.jobs
                    failed_records = collection_output.failed_records
                elif isinstance(collection_output, list):
                    jobs = collection_output
                    failed_records = 0
                else:
                    raise ApplicationError(
                        f"Collector {collector_name} returned unsupported result type"
                    )
            except ConfigurationError as exc:
                sources_failed += 1
                elapsed = time.perf_counter() - collector_started_at
                logger.warning(
                    "Collector failed | name=%s category=configuration elapsed=%.2fs error=%s",
                    collector_name,
                    elapsed,
                    exc,
                )
                collector_stats.append(
                    {
                        "name": collector_name,
                        "status": "failed",
                        "downloaded": 0,
                        "inserted": 0,
                        "duplicates": 0,
                        "failed": 1,
                    }
                )
                continue
            except ApplicationError as exc:
                sources_failed += 1
                elapsed = time.perf_counter() - collector_started_at
                logger.warning(
                    "Collector failed | name=%s category=application elapsed=%.2fs error=%s",
                    collector_name,
                    elapsed,
                    exc,
                )
                collector_stats.append(
                    {
                        "name": collector_name,
                        "status": "failed",
                        "downloaded": 0,
                        "inserted": 0,
                        "duplicates": 0,
                        "failed": 1,
                    }
                )
                continue
            except Exception as exc:
                sources_failed += 1
                elapsed = time.perf_counter() - collector_started_at
                logger.warning(
                    "Collector failed | name=%s category=unexpected elapsed=%.2fs error=%s",
                    collector_name,
                    elapsed,
                    exc,
                )
                collector_stats.append(
                    {
                        "name": collector_name,
                        "status": "failed",
                        "downloaded": 0,
                        "inserted": 0,
                        "duplicates": 0,
                        "failed": 1,
                    }
                )
                continue

            sources_succeeded += 1

            logger.info("Collector: %s", collector_name)
            logger.info("Downloaded: %s", len(jobs))
            summary = self.repository.insert_jobs(jobs)
            logger.info("Inserted: %s", summary["inserted"])
            logger.info("Duplicates: %s", summary["duplicates"])
            logger.info("Failed Records: %s", failed_records)

            collector_stats.append(
                {
                    "name": collector_name,
                    "status": "succeeded",
                    "downloaded": len(jobs),
                    "inserted": summary["inserted"],
                    "duplicates": summary["duplicates"],
                    "failed": failed_records,
                }
            )
            all_jobs.extend(jobs)
            total_downloaded += len(jobs)
            total_inserted += summary["inserted"]
            total_duplicates += summary["duplicates"]
            total_failed_records += failed_records

        elapsed = time.perf_counter() - started_at
        logger.info("Overall: Sources Attempted %s", sources_attempted)
        logger.info("Overall: Sources Succeeded %s", sources_succeeded)
        logger.info("Overall: Sources Failed %s", sources_failed)
        logger.info("Overall: Total Downloaded %s", total_downloaded)
        logger.info("Overall: Total Inserted %s", total_inserted)
        logger.info("Overall: Total Duplicates %s", total_duplicates)
        logger.info("Overall: Total Failed Records %s", total_failed_records)
        logger.info("Execution Time: %.2f seconds", elapsed)

        return {
            "sources_attempted": sources_attempted,
            "sources_succeeded": sources_succeeded,
            "sources_failed": sources_failed,
            "downloaded": total_downloaded,
            "inserted": total_inserted,
            "duplicates": total_duplicates,
            "failed": total_failed_records,
            "total": total_inserted + total_duplicates,
            "collector_stats": collector_stats,
        }


def build_collectors(settings: Settings) -> list[Collector]:
    registry = CollectorRegistry()

    if settings.enable_remoteok:
        registry.register("remoteok", RemoteOkCollector())
    else:
        registry.register("remoteok", DisabledCollector("RemoteOK"))

    if settings.enable_greenhouse:
        registry.register("greenhouse", GreenhouseCollector())
    else:
        registry.register("greenhouse", DisabledCollector("Greenhouse"))

    if settings.enable_adzuna:
        registry.register(
            "adzuna",
            AdzunaCollector(
                client=AdzunaClient(
                    app_id=settings.adzuna_app_id,
                    app_key=settings.adzuna_app_key,
                    country=settings.adzuna_country,
                )
            ),
        )
    else:
        registry.register("adzuna", DisabledCollector("Adzuna"))

    if settings.enable_jobicy:
        registry.register("jobicy", JobicyCollector())
    else:
        registry.register("jobicy", DisabledCollector("Jobicy"))

    if settings.enable_remotive:
        registry.register("remotive", RemotiveCollector())
    else:
        registry.register("remotive", DisabledCollector("Remotive"))

    if settings.enable_arbeitnow:
        registry.register("arbeitnow", ArbeitnowCollector())
    else:
        registry.register("arbeitnow", DisabledCollector("Arbeitnow"))

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
