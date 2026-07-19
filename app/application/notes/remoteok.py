"""RemoteOK-specific application notes provider."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.application.notes.base import NotesProvider

if TYPE_CHECKING:
    from domain.job import Job
    from app.recruiter.models import RecruiterContact


class RemoteOKNotesProvider(NotesProvider):
    """Extract RemoteOK-specific application notes."""

    @property
    def name(self) -> str:
        return "remoteok"

    def extract_notes(
        self,
        job: Job,
        recruiter_contact: RecruiterContact | None = None,
        resume_filename: str | None = None,
        recommendation_score: int | None = None,
        matched_skills: list[str] | None = None,
        missing_skills: list[str] | None = None,
    ) -> str:
        """Extract RemoteOK-specific notes.

        Extracts:
        - Recommendation score
        - Application keyword to mention
        - Application tag
        - Special instructions
        - Recruiter contact info

        Args:
            job: Job posting
            recruiter_contact: Discovered recruiter contact (if any)
            resume_filename: Name of resume file
            recommendation_score: Job score (0-100)
            matched_skills: List of matched skills (unused for RemoteOK notes)
            missing_skills: List of missing skills (unused for RemoteOK notes)

        Returns:
            Formatted application notes
        """
        lines = [self._format_notes_header(), ""]

        # Recommendation score
        if recommendation_score is not None:
            lines.append(self._format_field("Recommendation Score", f"{recommendation_score}%"))
            lines.append("")

        # RemoteOK-specific application instructions
        lines.append("=== REMOTEOK APPLICATION INSTRUCTIONS ===")
        keyword = self._extract_keyword(job.description or "")
        if keyword:
            lines.append(self._format_field("Mention Keyword", keyword))
        else:
            lines.append("Mention Keyword: NONE")
        
        tag = self._extract_tag(job.description or "")
        if tag:
            lines.append(self._format_field("Application Tag", tag))
        else:
            lines.append("Application Tag: NONE")
        
        instructions = self._extract_special_instructions(job.description or "")
        if instructions:
            lines.append(self._format_list_field("Special Instructions", instructions))
        else:
            lines.append("Special Instructions: NONE")
        lines.append("")

        # Application reference info
        lines.append("=== APPLICATION REFERENCE ===")
        lines.append(self._format_field("Job Source", job.source))
        if job.published_at:
            lines.append(self._format_field("Published", job.published_at.strftime("%Y-%m-%d")))
        lines.append(self._format_field("Job URL", job.url))
        lines.append(self._format_field("Resume File", resume_filename or "N/A"))
        recruiter_email = recruiter_contact.email if recruiter_contact else None
        lines.append(self._format_field("Recruiter Email", recruiter_email or "NOT FOUND"))
        if recruiter_contact and recruiter_contact.name:
            lines.append(self._format_field("Recruiter Name", recruiter_contact.name))
        lines.append("")

        # Add footer
        lines.append(self._format_notes_footer())

        return "\n".join(lines)

    def _extract_keyword(self, description: str) -> str | None:
        """Extract application keyword from description.

        Looks for pattern: Please mention the word <KEYWORD>

        Args:
            description: Job description

        Returns:
            Keyword if found
        """
        patterns = [
            r"(?:please\s+)?mention\s+(?:the\s+)?word[s]?[\s:]*([A-Z0-9]+)",
            r"keyword[\s:]*([A-Z0-9]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_tag(self, description: str) -> str | None:
        """Extract application tag from description.

        Looks for pattern: tag: <TAG>

        Args:
            description: Job description

        Returns:
            Tag if found
        """
        pattern = r"tag[\s:]*([A-Za-z0-9=+/]+)"
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return None

    def _extract_special_instructions(self, description: str) -> list[str]:
        """Extract special instructions from description.

        Looks for:
        - "Please mention"
        - "Must include"
        - "Include"
        - "Special instruction"

        Args:
            description: Job description

        Returns:
            List of special instructions
        """
        instructions = []

        patterns = [
            r"(?:please\s+)?mention[:\s]+([^.\n]+)",
            r"(?:must\s+)?include[:\s]+([^.\n]+)",
            r"special\s+instruction[s]?[:\s]+([^.\n]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, description, re.IGNORECASE)
            for match in matches:
                instruction = match.group(1).strip()
                if instruction and instruction not in instructions:
                    instructions.append(instruction)

        return instructions
