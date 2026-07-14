"""Workflow for discovering recruiter contacts for recommended jobs."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from app.recruiter.service import RecruiterDiscoveryService
from domain.job import Job

if TYPE_CHECKING:
    from infrastructure.sqlite.database import SQLiteDatabase
    from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class RecruiterDiscoveryWorkflow:
    """Orchestrate recruiter discovery for recommended jobs."""

    def __init__(
        self,
        database: SQLiteDatabase,
        job_repository: JobRepository,
    ) -> None:
        """Initialize workflow.

        Args:
            database: SQLiteDatabase instance
            job_repository: JobRepository instance
        """
        self.database = database
        self.job_repository = job_repository
        self.discovery_service = RecruiterDiscoveryService()

    def run(self) -> dict:
        """Discover recruiters for all recommended jobs without recruiter contact.

        Returns:
            Dictionary with statistics:
            - recommended_jobs: Total recommended jobs
            - already_discovered: Jobs with existing recruiter_email
            - recruiters_found: Number of recruiters successfully discovered
            - recruiters_missing: Number of jobs without recruiter found
            - execution_time: Time taken in seconds
        """
        start_time = time.time()

        try:
            # Get all recommended jobs (as raw rows for database field access)
            recommended_job_rows = self.job_repository.find_rows_by_status("RECOMMENDED")
            total_recommended = len(recommended_job_rows)

            if total_recommended == 0:
                logger.info("Recruiter discovery starting: 0 recommended jobs found")
                return {
                    "recommended_jobs": 0,
                    "already_discovered": 0,
                    "recruiters_found": 0,
                    "recruiters_missing": 0,
                    "execution_time": 0.0,
                }

            logger.info(f"Recruiter discovery starting: {total_recommended} recommended jobs found")

            recruiters_found = 0
            already_discovered = 0
            recruiters_missing = 0

            for job_row in recommended_job_rows:
                # Convert row to Job object for discovery
                job = Job(
                    id=job_row["job_id"],
                    title=job_row["title"],
                    company=job_row["company"],
                    location=job_row["location"],
                    url=job_row["url"],
                    source=job_row["source"],
                    description=job_row["description"],
                )

                # Check if already has recruiter info
                if job_row["recruiter_email"]:
                    already_discovered += 1
                    logger.debug(f"Job {job.id} already has recruiter: {job_row['recruiter_email']}")
                    continue

                # Attempt discovery
                contact = self.discovery_service.discover(job)

                if contact:
                    self.job_repository.update_recruiter(
                        job_id=job.id,
                        email=contact.email,
                        name=contact.name,
                        source=contact.source,
                        confidence=contact.confidence,
                    )
                    recruiters_found += 1
                    logger.info(
                        f"Recruiter discovered for job {job.id}: "
                        f"{contact.email} (source={contact.source}, confidence={contact.confidence})"
                    )
                else:
                    recruiters_missing += 1
                    logger.debug(f"No recruiter found for job {job.id}")

            execution_time = time.time() - start_time

            logger.info(
                f"Recruiter discovery completed: "
                f"{recruiters_found} found, {recruiters_missing} missing, "
                f"time={execution_time:.2f}s"
            )

            return {
                "recommended_jobs": total_recommended,
                "already_discovered": already_discovered,
                "recruiters_found": recruiters_found,
                "recruiters_missing": recruiters_missing,
                "execution_time": execution_time,
            }

        except Exception as e:
            logger.error(f"Recruiter discovery workflow failed: {e}", exc_info=True)
            raise
