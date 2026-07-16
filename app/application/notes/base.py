"""Base class for application notes providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.job import Job
    from app.recruiter.models import RecruiterContact


class NotesProvider(ABC):
    """Base class for extracting source-specific application notes."""

    @abstractmethod
    def extract_notes(
        self,
        job: Job,
        recruiter_contact: RecruiterContact | None = None,
        resume_filename: str | None = None,
        recommendation_score: int | None = None,
        matched_skills: list[str] | None = None,
        missing_skills: list[str] | None = None,
    ) -> str:
        """Extract application notes for the job.

        Args:
            job: Job posting
            recruiter_contact: Discovered recruiter contact (if any)
            resume_filename: Name of resume file
            recommendation_score: Job score (0-100)
            matched_skills: List of matched skills
            missing_skills: List of missing skills

        Returns:
            Formatted application notes string
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass

    def _format_notes_header(self) -> str:
        """Format the application notes header."""
        return "=" * 50 + "\n\nAPPLICATION NOTES (DELETE BEFORE SENDING)\n\n" + "=" * 50

    def _format_notes_footer(self) -> str:
        """Format the application notes footer."""
        return "=" * 50 + "\n\nEND APPLICATION NOTES\n\n" + "=" * 50

    def _format_field(self, label: str, value: str | int | None) -> str:
        """Format a field in the notes.
        
        Args:
            label: Field label
            value: Field value (or None for "NOT FOUND")
            
        Returns:
            Formatted field string
        """
        display_value = str(value) if value is not None else "NOT FOUND"
        return f"{label}: {display_value}"

    def _format_list_field(self, label: str, items: list[str] | None) -> str:
        """Format a list field in the notes.
        
        Args:
            label: Field label
            items: List of items (or empty/None for "NONE")
            
        Returns:
            Formatted field string
        """
        if items and len(items) > 0:
            return f"{label}:\n  - " + "\n  - ".join(items)
        return f"{label}: NONE"

    def _truncate_text(self, text: str | None, max_chars: int = 800) -> str:
        """Truncate text to max length.
        
        Args:
            text: Text to truncate
            max_chars: Maximum characters
            
        Returns:
            Truncated text or "N/A"
        """
        if not text:
            return "N/A"
        if len(text) <= max_chars:
            return text
        # Truncate and clean up
        truncated = text[:max_chars].strip()
        # Try to end at sentence boundary
        last_period = truncated.rfind(".")
        if last_period > max_chars - 100:
            truncated = truncated[:last_period + 1]
        return truncated + "..."
