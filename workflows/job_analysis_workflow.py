"""Workflow for analyzing recommended jobs using AI provider."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from core.analysis.mock_provider import MockProvider
from infrastructure.sqlite.job_analysis_repository import JobAnalysisRepository

if TYPE_CHECKING:
    from config.profile import Profile
    from core.analysis.provider import AIProvider
    from infrastructure.sqlite.database import SQLiteDatabase
    from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class JobAnalysisWorkflow:
    """Orchestrate analysis of recommended jobs."""

    def __init__(
        self,
        database: SQLiteDatabase,
        job_repository: JobRepository,
        profile: Profile,
        provider: AIProvider | None = None,
    ) -> None:
        """Initialize workflow.
        
        Args:
            database: SQLiteDatabase instance
            job_repository: JobRepository instance
            profile: Candidate profile
            provider: AI provider (defaults to MockProvider)
        """
        self.database = database
        self.job_repository = job_repository
        self.profile = profile
        self.provider = provider or MockProvider(profile)
        self.analysis_repository = JobAnalysisRepository(database)

    def run(self) -> dict:
        """Analyze all recommended jobs not yet analyzed.
        
        Returns:
            Dictionary with statistics:
            - recommended_jobs: Total recommended jobs
            - already_analyzed: Jobs already analyzed
            - new_analyses: Newly analyzed jobs
            - execution_time: Time taken in seconds
        """
        start_time = time.time()

        try:
            # Get all recommended jobs
            recommended_jobs = self.job_repository.find_by_status("RECOMMENDED")
            total_recommended = len(recommended_jobs)

            logger.info(f"Job analysis starting: {total_recommended} recommended jobs found")

            already_analyzed = 0
            new_analyses = 0

            for job in recommended_jobs:
                # Skip if already analyzed by this provider
                if self.analysis_repository.has_analysis(job.id, self.provider.name):
                    already_analyzed += 1
                    logger.debug(f"Job already analyzed: {job.id}")
                    continue

                # Analyze job
                try:
                    analysis = self.provider.analyze(job)
                    self.analysis_repository.save(analysis)
                    new_analyses += 1
                    logger.debug(f"Job analyzed: {job.id} - Confidence: {analysis.confidence}%")
                except Exception as exc:
                    logger.error(f"Failed to analyze job {job.id}: {exc}")

            execution_time = time.time() - start_time

            return {
                "recommended_jobs": total_recommended,
                "already_analyzed": already_analyzed,
                "new_analyses": new_analyses,
                "execution_time": execution_time,
            }
        except Exception as exc:
            logger.error(f"Job analysis workflow failed: {exc}")
            return {
                "recommended_jobs": 0,
                "already_analyzed": 0,
                "new_analyses": 0,
                "execution_time": time.time() - start_time,
            }
