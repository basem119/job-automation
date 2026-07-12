from __future__ import annotations

import sqlite3
from datetime import datetime

from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase


class JobRepository:
    """Storage repository for inserting jobs into SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def insert_jobs(self, jobs: list[Job]) -> int:
        if not jobs:
            return 0

        inserted_count = 0
        for job in jobs:
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
                    published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            inserted_count += 1

        self.database.connection.commit()
        return inserted_count
