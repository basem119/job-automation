from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase

logger = logging.getLogger("job_automation")


class JobRepository:
    """Storage repository for inserting jobs into SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def load_new_jobs(self) -> list[Job]:
        rows = self.database.connection.execute(
            "SELECT * FROM jobs WHERE status = 'NEW' ORDER BY id"
        ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def update_status(self, job_id: int | str, status: str) -> None:
        self.database.connection.execute(
            "UPDATE jobs SET status = ? WHERE job_id = ?",
            (status.strip().upper(), job_id),
        )
        self.database.connection.commit()

    def update_job_result(self, job_id: int | str, status: str, score: int, reason: str) -> None:
        """Update job status, score, and filter reason atomically."""
        self.database.connection.execute(
            "UPDATE jobs SET status = ?, score = ?, filter_reason = ? WHERE job_id = ?",
            (status.strip().upper(), score, reason, job_id),
        )
        self.database.connection.commit()

    def update_recommendation(
        self, job_id: int | str, status: str, score: int, summary: str, details: list
    ) -> None:
        """Update job with recommendation score, summary, and details atomically."""
        details_json = json.dumps([
            {"rule": d.rule, "score": d.score, "reason": d.reason}
            for d in details
        ]) if details else None
        
        self.database.connection.execute(
            """
            UPDATE jobs 
            SET status = ?, recommendation_score = ?, 
                recommendation_summary = ?, recommendation_details = ?
            WHERE job_id = ?
            """,
            (status.strip().upper(), score, summary, details_json, job_id),
        )
        self.database.connection.commit()

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
                        hash,
                    status,
                    technologies
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        (job.status or "NEW").strip().upper(),
                        json.dumps(job.technologies) if job.technologies else None,
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
    def _row_to_job(row: Any) -> Job:
        technologies = None
        if row["technologies"]:
            try:
                technologies = json.loads(row["technologies"])
            except (json.JSONDecodeError, TypeError):
                technologies = None

        return Job(
            id=str(row["job_id"]),
            title=row["title"],
            company=row["company"],
            location=row["location"],
            description=row["description"] or "",
            url=row["url"],
            source=row["source"],
            published_at=row["published_at"],
            status=row["status"],
            technologies=technologies,
        )

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
