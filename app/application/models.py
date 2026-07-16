"""Application data model."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.recruiter.models import RecruiterContact
from config.profile import Profile
from domain.job import Job


@dataclass
class Application:
    """Represents a job application being prepared for submission."""

    job: Job
    candidate_profile: Profile
    resume_path: Path
    email_subject: str
    email_body: str
    application_notes: str
    recruiter_contact: RecruiterContact | None = None

    def validate(self) -> tuple[bool, str]:
        """Validate application has all required fields.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.job or not self.job.id:
            return False, "Job is required"
        
        if not self.candidate_profile:
            return False, "Candidate profile is required"
        
        if not self.resume_path:
            return False, "Resume path is required"
        
        if not self.resume_path.exists():
            return False, f"Resume file not found: {self.resume_path}"
        
        if not self.email_subject or not self.email_subject.strip():
            return False, "Email subject is required"
        
        if not self.email_body or not self.email_body.strip():
            return False, "Email body is required"
        
        if not self.application_notes:
            return False, "Application notes are required"
        
        return True, ""

    @property
    def recipient_email(self) -> str | None:
        """Get recipient email if recruiter was found."""
        return self.recruiter_contact.email if self.recruiter_contact else None

    @property
    def recipient_name(self) -> str | None:
        """Get recipient name if recruiter was found."""
        return self.recruiter_contact.name if self.recruiter_contact else None
