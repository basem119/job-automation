"""Greenhouse-specific application notes provider."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.application.notes.base import NotesProvider

if TYPE_CHECKING:
    from domain.job import Job
    from app.recruiter.models import RecruiterContact


class GreenhouseNotesProvider(NotesProvider):
    """Extract Greenhouse-specific application notes."""

    @property
    def name(self) -> str:
        return "greenhouse"

    def extract_notes(
        self,
        job: Job,
        recruiter_contact: RecruiterContact | None = None,
        resume_filename: str | None = None,
        recommendation_score: int | None = None,
        matched_skills: list[str] | None = None,
        missing_skills: list[str] | None = None,
    ) -> str:
        """Extract Greenhouse-specific notes.

        Extracts:
        - Recommendation score
        - Application deadline (if available)
        - Recruiter contact info
        - Resume filename

        Args:
            job: Job posting
            recruiter_contact: Discovered recruiter contact (if any)
            resume_filename: Name of resume file
            recommendation_score: Job score (0-100)
            matched_skills: List of matched skills (unused for Greenhouse notes)
            missing_skills: List of missing skills (unused for Greenhouse notes)

        Returns:
            Formatted application notes
        """
        lines = [self._format_notes_header(), ""]

        # Recommendation score
        if recommendation_score is not None:
            lines.append(self._format_field("Recommendation Score", f"{recommendation_score}%"))
            lines.append("")

        # Greenhouse-specific information
        lines.append("=== GREENHOUSE INFORMATION ===")
        deadline = self._extract_deadline(job.description or "")
        if deadline:
            lines.append(self._format_field("Application Deadline", deadline))
        else:
            lines.append("Application Deadline: NONE")
        lines.append("")

        # Application reference info
        lines.append("=== APPLICATION REFERENCE ===")
        lines.append(self._format_field("Job Source", job.source))
        if job.published_at:
            lines.append(self._format_field("Published", job.published_at.strftime("%Y-%m-%d")))
        lines.append(self._format_field("Resume File", resume_filename or "N/A"))
        recruiter_email = recruiter_contact.email if recruiter_contact else None
        lines.append(self._format_field("Recruiter Email", recruiter_email or "NOT FOUND"))
        if recruiter_contact and recruiter_contact.name:
            lines.append(self._format_field("Recruiter Name", recruiter_contact.name))
        lines.append("")

        # Add footer
        lines.append(self._format_notes_footer())

        return "\n".join(lines)

    def _extract_deadline(self, description: str) -> str | None:
        """Extract application deadline from description.

        Looks for date patterns and deadline mentions.

        Args:
            description: Job description

        Returns:
            Deadline if found
        """
        patterns = [
            r"(?:deadline|closing\s+date|apply\s+by)[:\s]+([^\n]+?)(?:\.|,|$)",
            r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1).strip() if match.lastindex else match.group(0).strip()

        return None

    def _extract_application_url(self, url: str) -> str | None:
        """Extract Greenhouse application URL.

        Greenhouse URLs typically follow pattern:
        company.greenhouse.io/jobs/job-id

        Args:
            url: Job URL

        Returns:
            Application URL if it's Greenhouse
        """
        if "greenhouse.io" in url.lower():
            return url

        return None
