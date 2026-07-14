"""Repository pattern for job analysis database access."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from core.analysis.analysis_result import AnalysisResult
from core.exceptions import ApplicationError

if TYPE_CHECKING:
    from infrastructure.sqlite.database import SQLiteDatabase

logger = logging.getLogger("job_automation")


class JobAnalysisRepository:
    """Repository for job analysis data."""

    def __init__(self, database: SQLiteDatabase) -> None:
        """Initialize repository with database connection.
        
        Args:
            database: SQLiteDatabase instance
        """
        self.database = database

    def save(self, analysis: AnalysisResult) -> None:
        """Save analysis result to database.
        
        Args:
            analysis: AnalysisResult to save
            
        Raises:
            ApplicationError: If save fails
        """
        try:
            strengths_json = json.dumps(analysis.strengths)
            missing_skills_json = json.dumps(analysis.missing_skills)

            self.database.connection.execute(
                """
                INSERT OR REPLACE INTO job_analysis 
                (job_id, provider, match_summary, strengths, missing_skills, 
                 recommended_resume, email_highlights, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    analysis.job_id,
                    analysis.provider,
                    analysis.match_summary,
                    strengths_json,
                    missing_skills_json,
                    analysis.recommended_resume,
                    analysis.email_highlights,
                    analysis.confidence,
                ),
            )
            self.database.connection.commit()
            logger.debug(f"Analysis saved: {analysis.job_id} by {analysis.provider}")
        except Exception as exc:
            raise ApplicationError(f"Failed to save analysis: {exc}") from exc

    def get_by_job_and_provider(self, job_id: str, provider: str) -> AnalysisResult | None:
        """Get analysis by job and provider.
        
        Args:
            job_id: Job ID
            provider: Provider name
            
        Returns:
            AnalysisResult if found, None otherwise
        """
        try:
            row = self.database.connection.execute(
                """
                SELECT job_id, provider, match_summary, strengths, missing_skills,
                       recommended_resume, email_highlights, confidence
                FROM job_analysis
                WHERE job_id = ? AND provider = ?
                """,
                (job_id, provider),
            ).fetchone()

            if not row:
                return None

            return AnalysisResult(
                job_id=row["job_id"],
                provider=row["provider"],
                match_summary=row["match_summary"],
                strengths=json.loads(row["strengths"]),
                missing_skills=json.loads(row["missing_skills"]),
                recommended_resume=row["recommended_resume"],
                email_highlights=row["email_highlights"],
                confidence=row["confidence"],
            )
        except Exception as exc:
            logger.error(f"Failed to get analysis: {exc}")
            return None

    def get_all_by_job(self, job_id: str) -> list[AnalysisResult]:
        """Get all analyses for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of AnalysisResult
        """
        try:
            rows = self.database.connection.execute(
                """
                SELECT job_id, provider, match_summary, strengths, missing_skills,
                       recommended_resume, email_highlights, confidence
                FROM job_analysis
                WHERE job_id = ?
                ORDER BY created_at DESC
                """,
                (job_id,),
            ).fetchall()

            return [
                AnalysisResult(
                    job_id=row["job_id"],
                    provider=row["provider"],
                    match_summary=row["match_summary"],
                    strengths=json.loads(row["strengths"]),
                    missing_skills=json.loads(row["missing_skills"]),
                    recommended_resume=row["recommended_resume"],
                    email_highlights=row["email_highlights"],
                    confidence=row["confidence"],
                )
                for row in rows
            ]
        except Exception as exc:
            logger.error(f"Failed to get analyses: {exc}")
            return []

    def count_by_provider(self, provider: str) -> int:
        """Count analyses by provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Count of analyses
        """
        try:
            row = self.database.connection.execute(
                "SELECT COUNT(*) as count FROM job_analysis WHERE provider = ?",
                (provider,),
            ).fetchone()
            return row["count"] if row else 0
        except Exception as exc:
            logger.error(f"Failed to count analyses: {exc}")
            return 0

    def has_analysis(self, job_id: str, provider: str) -> bool:
        """Check if analysis exists.
        
        Args:
            job_id: Job ID
            provider: Provider name
            
        Returns:
            True if analysis exists
        """
        try:
            row = self.database.connection.execute(
                "SELECT 1 FROM job_analysis WHERE job_id = ? AND provider = ? LIMIT 1",
                (job_id, provider),
            ).fetchone()
            return row is not None
        except Exception as exc:
            logger.error(f"Failed to check analysis: {exc}")
            return False
