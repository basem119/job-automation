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

    def run(self) -> dict:
        """Evaluate all NEW jobs, assign scores, update status and reason."""
        started_at = time.perf_counter()
        jobs = self.repository.load_new_jobs()
        evaluated = len(jobs)
        accepted = 0
        rejected = 0
        scores: list[int] = []

        for job in jobs:
            # Evaluate all rules
            results = [rule.evaluate(job) for rule in self.rules]

            # Check for rejections
            rejected_result = next((r for r in results if not r.passed), None)
            if rejected_result:
                self.repository.update_job_result(job.id, "REJECTED", 0, rejected_result.reason)
                rejected += 1
            else:
                # Calculate total score from all rule results
                total_score = sum(r.score for r in results)
                reason_parts = [r.reason for r in results if r.reason]
                combined_reason = " | ".join(reason_parts)

                self.repository.update_job_result(job.id, "FILTERED", total_score, combined_reason)
                scores.append(total_score)
                accepted += 1

        elapsed = time.perf_counter() - started_at
        
        # Calculate statistics
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0

        logger.info("Jobs evaluated: %s", evaluated)
        logger.info("Jobs filtered: %s", accepted)
        logger.info("Jobs rejected: %s", rejected)
        logger.info("Average score: %.2f", avg_score)
        logger.info("Highest score: %s", max_score)
        logger.info("Lowest score: %s", min_score)
        logger.info("Execution time: %.2f seconds", elapsed)

        return {
            "evaluated": evaluated,
            "filtered": accepted,
            "rejected": rejected,
            "average_score": avg_score,
            "highest_score": max_score,
            "lowest_score": min_score,
            "execution_time": elapsed,
        }
