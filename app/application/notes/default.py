"""Default application notes provider."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.notes.base import NotesProvider

if TYPE_CHECKING:
    from domain.job import Job
    from app.recruiter.models import RecruiterContact


class DefaultNotesProvider(NotesProvider):
    """Generate generic application notes for any job source."""

    @property
    def name(self) -> str:
        return "default"

    def extract_notes(
        self,
        job: Job,
        recruiter_contact: RecruiterContact | None = None,
        resume_filename: str | None = None,
        recommendation_score: int | None = None,
        matched_skills: list[str] | None = None,
        missing_skills: list[str] | None = None,
    ) -> str:
        """Extract comprehensive application notes.

        Args:
            job: Job posting
            recruiter_contact: Discovered recruiter contact (if any)
            resume_filename: Name of resume file
            recommendation_score: Job score (0-100)
            matched_skills: List of matched skills
            missing_skills: List of missing skills

        Returns:
            Formatted application notes
        """
        lines = [self._format_notes_header(), ""]

        # Recommendation score (not in email body)
        if recommendation_score is not None:
            lines.append(self._format_field("Recommendation Score", f"{recommendation_score}%"))
            lines.append("")

        # Job details summary (metadata reference)
        lines.append("=== JOB DETAILS ===")
        lines.append(self._format_field("Source", job.source))
        if job.published_at:
            lines.append(self._format_field("Published", job.published_at.strftime("%Y-%m-%d")))
        lines.append("")

        # Application reference info
        lines.append("=== APPLICATION REFERENCE ===")
        lines.append(self._format_field("Resume File", resume_filename or "N/A"))
        recruiter_email = recruiter_contact.email if recruiter_contact else None
        lines.append(self._format_field("Recruiter Email", recruiter_email or "NOT FOUND"))
        if recruiter_contact and recruiter_contact.name:
            lines.append(self._format_field("Recruiter Name", recruiter_contact.name))
        lines.append("")

        # Add footer
        lines.append(self._format_notes_footer())

        return "\n".join(lines)
