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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_status_column()
            self._ensure_hash_column_and_index()
            self._ensure_technologies_column()
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


    @staticmethod
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
