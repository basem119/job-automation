from __future__ import annotations

import hashlib
import logging
from typing import Any

from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase

logger = logging.getLogger("job_automation")


class JobRepository:
    """Storage repository for inserting jobs into SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def insert_jobs(self, jobs: list[Job]) -> dict[str, int]:
        if not jobs:
            return {"inserted": 0, "duplicates": 0, "total": 0}

        inserted_count = 0
        duplicate_count = 0

        for job in jobs:
            job_hash = self.build_hash(job)
            existing = self.database.connection.execute(
                "SELECT 1 FROM jobs WHERE hash = ?",
                (job_hash,),
            ).fetchone()

            if existing is not None:
                duplicate_count += 1
                logger.info("Duplicate job skipped: %s", job_hash)
                continue

            try:
                self.database.connection.execute(
                    """
                    INSERT INTO jobs (
                        job_id,
                        source,
                        company,
                        title,
                        location,
                        url,
                        description,
                        published_at,
                        hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.id,
                        job.source,
                        job.company,
                        job.title,
                        job.location,
                        job.url,
                        job.description,
                        job.published_at.isoformat() if job.published_at else None,
                        job_hash,
                    ),
                )
            except Exception:
                duplicate_count += 1
                logger.warning("Duplicate job skipped due to database constraint: %s", job_hash)
                continue

            inserted_count += 1

        self.database.connection.commit()
        return {
            "inserted": inserted_count,
            "duplicates": duplicate_count,
            "total": inserted_count + duplicate_count,
        }

    @staticmethod
    def build_hash(job: Job) -> str:
        source = (job.source or "").strip().lower()
        job_id = (job.id or "").strip()

        if not job_id:
            seed = "|".join(
                [
                    source,
                    (job.company or "").strip().lower(),
                    (job.title or "").strip().lower(),
                    (job.url or "").strip().lower(),
                ]
            )
        else:
            seed = "|".join([source, job_id])

        return hashlib.sha256(seed.encode("utf-8")).hexdigest()
