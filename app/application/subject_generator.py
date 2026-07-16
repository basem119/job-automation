"""Email subject generation."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.job import Job


class SubjectGenerator:
    """Generate professional email subjects for job applications."""

    @staticmethod
    def generate(job: Job) -> str:
        """Generate a professional subject line.

        Format: Application – {Role} – {Company}

        Args:
            job: Job posting to generate subject for

        Returns:
            Professional email subject
        """
        if not job or not job.company or not job.title:
            return "Job Application"

        # Use exact job title and company name
        company = job.company.strip()
        title = job.title.strip()

        return f"Application – {title} – {company}"
