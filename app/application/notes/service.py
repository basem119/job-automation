"""Application notes service."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.notes.default import DefaultNotesProvider
from app.application.notes.greenhouse import GreenhouseNotesProvider
from app.application.notes.remoteok import RemoteOKNotesProvider

if TYPE_CHECKING:
    from domain.job import Job
    from app.recruiter.models import RecruiterContact

logger = logging.getLogger("job_automation")


class ApplicationNotesService:
    """Service to generate application notes for jobs."""

    def __init__(self) -> None:
        """Initialize with default providers."""
        # Map job sources to their providers
        self.providers = {
            "remoteok": RemoteOKNotesProvider(),
            "greenhouse": GreenhouseNotesProvider(),
        }
        self.default_provider = DefaultNotesProvider()

    def generate(
        self,
        job: Job,
        recruiter_contact: RecruiterContact | None = None,
        resume_filename: str | None = None,
        recommendation_score: int | None = None,
        matched_skills: list[str] | None = None,
        missing_skills: list[str] | None = None,
    ) -> str:
        """Generate application notes for a job.

        Selects source-specific provider if available, otherwise uses default.

        Args:
            job: Job posting
            recruiter_contact: Discovered recruiter contact (if any)
            resume_filename: Name of resume file being used
            recommendation_score: Job recommendation score (0-100)
            matched_skills: List of matched skills
            missing_skills: List of missing skills

        Returns:
            Formatted application notes
        """
        source = (job.source or "").lower().strip()
        provider = self.providers.get(source, self.default_provider)

        logger.debug(f"Using notes provider: {provider.name}")
        return provider.extract_notes(
            job,
            recruiter_contact=recruiter_contact,
            resume_filename=resume_filename,
            recommendation_score=recommendation_score,
            matched_skills=matched_skills or [],
            missing_skills=missing_skills or [],
        )
