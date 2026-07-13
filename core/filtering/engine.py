from __future__ import annotations

import logging
import time
from pathlib import Path

from config.preferences import Preferences
from core.filtering.rules import ExcludedKeywordRule, LocationRule, TechnologyRule, TitleRule
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class FilteringEngine:
    """Filter persisted jobs against configured preferences and update status."""

    def __init__(
        self,
        database: SQLiteDatabase | None = None,
        repository: JobRepository | None = None,
        preferences: Preferences | None = None,
    ) -> None:
        self.database = database or SQLiteDatabase()
        self.repository = repository or JobRepository(self.database)
        self.preferences = preferences or Preferences.load(Path("config/preferences.yaml"))
        self.rules = [
            LocationRule(self.preferences),
            TitleRule(self.preferences),
            TechnologyRule(self.preferences),
            ExcludedKeywordRule(self.preferences),
        ]

    def run(self) -> dict[str, int]:
        started_at = time.perf_counter()
        jobs = self.repository.load_new_jobs()
        evaluated = len(jobs)
        accepted = 0
        rejected = 0

        for job in jobs:
            passed = all(rule.evaluate(job) for rule in self.rules)
            if passed:
                self.repository.update_status(job.id, "FILTERED")
                accepted += 1
            else:
                self.repository.update_status(job.id, "REJECTED")
                rejected += 1

        elapsed = time.perf_counter() - started_at
        logger.info("Jobs evaluated: %s", evaluated)
        logger.info("Jobs accepted: %s", accepted)
        logger.info("Jobs rejected: %s", rejected)
        logger.info("Execution time: %.2f seconds", elapsed)

        return {
            "evaluated": evaluated,
            "accepted": accepted,
            "rejected": rejected,
            "execution_time": elapsed,
        }
