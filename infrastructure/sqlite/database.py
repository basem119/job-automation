from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from core.exceptions import ApplicationError
from utils.filesystem import ensure_directory, project_root

logger = logging.getLogger("job_automation")


class SQLiteDatabase:
    """SQLite database wrapper with minimal initialization for milestone 2."""

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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.connection.commit()
        except sqlite3.Error as exc:
            raise ApplicationError(f"Failed to initialize SQLite database: {exc}") from exc

    def close(self) -> None:
        self.connection.close()
