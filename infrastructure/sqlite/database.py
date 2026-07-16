from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from core.exceptions import ApplicationError
from utils.filesystem import ensure_directory, project_root

logger = logging.getLogger("job_automation")


class SQLiteDatabase:
    """SQLite database wrapper with minimal initialization for milestone 3."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        resolved_path = Path(database_path or project_root() / "data" / "jobs.db")
        ensure_directory(resolved_path.parent)
        self.database_path = resolved_path
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        logger.info("Database initialization")
        self._initialize()

    def _initialize(self) -> None:
        try:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    location TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT,
                    published_at TEXT,
                    hash TEXT,
                    status TEXT NOT NULL DEFAULT 'NEW',
                    technologies TEXT,
                    recommendation_score INTEGER DEFAULT 0,
                    recommendation_summary TEXT,
                    recommendation_details TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_status_column()
            self._ensure_hash_column_and_index()
            self._ensure_technologies_column()
            self._ensure_recommendation_columns()
            self._ensure_recruiter_columns()
            self._ensure_draft_columns()
            self._create_job_analysis_table()
            self.connection.commit()
        except sqlite3.Error as exc:
            raise ApplicationError(f"Failed to initialize SQLite database: {exc}") from exc

    def _ensure_status_column(self) -> None:
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "status" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'NEW'")

    def _ensure_hash_column_and_index(self) -> None:
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "hash" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN hash TEXT")

        rows = self.connection.execute(
            "SELECT id, source, job_id, company, title, url FROM jobs WHERE hash IS NULL OR hash = ''"
        ).fetchall()
        for row in rows:
            computed_hash = self._build_hash_from_row(row)
            try:
                self.connection.execute("UPDATE jobs SET hash = ? WHERE id = ?", (computed_hash, row["id"]))
            except sqlite3.IntegrityError:
                self.connection.execute("UPDATE jobs SET hash = ? WHERE id = ?", (f"{computed_hash}-{row['id']}", row["id"]))

    def _ensure_technologies_column(self) -> None:
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "technologies" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN technologies TEXT")

    def _ensure_score_column(self) -> None:
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "score" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN score INTEGER DEFAULT 0")

    def _ensure_filter_reason_column(self) -> None:
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "filter_reason" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN filter_reason TEXT")

    def _ensure_recommendation_columns(self) -> None:
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "recommendation_score" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN recommendation_score INTEGER DEFAULT 0")
        
        if "recommendation_summary" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN recommendation_summary TEXT")
        
        if "recommendation_details" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN recommendation_details TEXT")

    def _ensure_recruiter_columns(self) -> None:
        """Ensure recruiter columns exist in jobs table."""
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "recruiter_email" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN recruiter_email TEXT")
        
        if "recruiter_name" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN recruiter_name TEXT")
        
        if "recruiter_source" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN recruiter_source TEXT")
        
        if "recruiter_confidence" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN recruiter_confidence INTEGER DEFAULT 0")

    def _ensure_draft_columns(self) -> None:
        """Ensure draft-related columns exist in jobs table."""
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")]

        if "draft_id" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN draft_id TEXT")
        
        if "draft_created_at" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN draft_created_at TEXT")
        
        if "processing_notes" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN processing_notes TEXT")

    def _create_job_analysis_table(self) -> None:
        """Create job_analysis table for AI provider analysis results."""
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS job_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                match_summary TEXT,
                strengths TEXT,
                missing_skills TEXT,
                recommended_resume TEXT,
                email_highlights TEXT,
                confidence INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, provider),
                FOREIGN KEY(job_id) REFERENCES jobs(job_id)
            )
            """
        )


    def _build_hash_from_row(row: sqlite3.Row) -> str:
        source = (row["source"] or "").strip().lower()
        job_id = (row["job_id"] or "").strip()

        if not job_id:
            seed = "|".join(
                [
                    source,
                    (row["company"] or "").strip().lower(),
                    (row["title"] or "").strip().lower(),
                    (row["url"] or "").strip().lower(),
                ]
            )
        else:
            seed = "|".join([source, job_id])

        return __import__("hashlib").sha256(seed.encode("utf-8")).hexdigest()

    def close(self) -> None:
        self.connection.close()
