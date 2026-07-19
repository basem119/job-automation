"""Application builder."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.application.email_template import EmailTemplate
from app.application.models import Application
from app.application.notes.service import ApplicationNotesService
from app.application.subject_generator import SubjectGenerator
from config.settings import Settings

if TYPE_CHECKING:
    from app.recruiter.models import RecruiterContact
    from config.profile import Profile
    from domain.job import Job

logger = logging.getLogger("job_automation")


class ApplicationBuilder:
    """Build Application objects for job submissions."""

    def __init__(
        self,
        resume_path: Path | None = None,
        template_dir: Path | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize builder.

        Args:
            resume_path: Path to resume file. If None, will be resolved from profile.
            template_dir: Directory containing email templates
            settings: Loaded application settings
        """
        self.resume_path = resume_path
        self.template_dir = template_dir
        self.settings = settings or Settings.load()
        self.notes_service = ApplicationNotesService()
        self.email_template = EmailTemplate(template_dir)

    def build(
        self,
        job: Job,
        profile: Profile,
        recruiter_contact: RecruiterContact | None = None,
        recommendation_score: int | None = None,
        matched_skills: list[str] | None = None,
        missing_skills: list[str] | None = None,
    ) -> Application | None:
        """Build an Application object.

        Args:
            job: Job posting
            profile: Candidate profile
            recruiter_contact: Discovered recruiter contact (optional)
            recommendation_score: Job recommendation score (0-100)
            matched_skills: List of skills that match job requirements
            missing_skills: List of skills missing from candidate profile

        Returns:
            Application object, or None if building fails
        """
        try:
            # Resolve resume path
            resume_path = self._resolve_resume_path(profile)
            if not resume_path:
                logger.warning(f"No resume found for job {job.id}")
                return None

            # Generate email subject
            subject = SubjectGenerator.generate(job)

            # Generate email body
            body = self.email_template.generate(job, profile)

            # Generate application notes with all metadata
            notes = self.notes_service.generate(
                job,
                recruiter_contact=recruiter_contact,
                resume_filename=resume_path.name,
                recommendation_score=recommendation_score,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
            )

            # Create application
            application = Application(
                job=job,
                candidate_profile=profile,
                resume_path=resume_path,
                email_subject=subject,
                email_body=body,
                application_notes=notes,
                recruiter_contact=recruiter_contact,
            )

            # Validate
            is_valid, error_msg = application.validate()
            if not is_valid:
                logger.warning(f"Application validation failed for job {job.id}: {error_msg}")
                return None

            logger.debug(f"Application built for job {job.id}: {subject}")
            return application

        except Exception as e:
            logger.error(f"Failed to build application for job {job.id}: {e}", exc_info=True)
            return None

    def _resolve_resume_path(self, profile: Profile) -> Path | None:
        """Resolve resume file path from profile.

        Args:
            profile: Candidate profile

        Returns:
            Path to resume file, or None if not found
        """
        # If explicitly set, use that
        if self.resume_path:
            path = Path(self.resume_path)
            if path.exists():
                return path
            return None

        resume_dir = self.settings.resume_directory

        # Use profile's default resume
        # Profile.resume() gets resume by name. Use first available.
        if hasattr(profile, "resume_profiles") and profile.resume_profiles:
            # Get first resume profile (backend by default)
            for name, filename in profile.resume_profiles.items():
                resume_path = resume_dir / filename
                if resume_path.exists():
                    logger.debug(f"Found resume: {name} -> {resume_path}")
                    return resume_path

        # Fallback: use the first PDF in configured resume directory
        if resume_dir.exists():
            pdfs = list(resume_dir.glob("*.pdf"))
            if pdfs:
                logger.debug(f"Using fallback resume: {pdfs[0]}")
                return pdfs[0]

        logger.warning(f"No resume found in {resume_dir}")
        return None
