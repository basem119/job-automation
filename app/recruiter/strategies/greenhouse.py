"""Greenhouse job board recruiter discovery strategy."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.recruiter.base import DiscoveryStrategy
from app.recruiter.models import RecruiterContact

if TYPE_CHECKING:
    from domain.job import Job


class GreenhouseStrategy(DiscoveryStrategy):
    """Extract recruiter contact from Greenhouse job board metadata."""

    @property
    def name(self) -> str:
        return "greenhouse"

    def discover(self, job: Job) -> RecruiterContact | None:
        """Inspect Greenhouse job payload for recruiter email.

        Greenhouse embeds recruiter information in:
        - Job URL (company.greenhouse.io pattern)
        - Description metadata
        - Common application email pattern

        Args:
            job: Job to discover recruiter for

        Returns:
            RecruiterContact if found, None otherwise
        """
        if not job.url:
            return None

        # Check if this is a Greenhouse job
        if "greenhouse.io" not in job.url.lower():
            return None

        # Try to extract recruiter email from description
        recruiter_email = self._extract_from_description(job.description or "")
        if recruiter_email:
            return RecruiterContact(
                email=recruiter_email,
                name="Greenhouse Recruiter",
                source="greenhouse_metadata",
                confidence=85,
            )

        return None

    def _extract_from_description(self, description: str) -> str | None:
        """Extract potential recruiter email from job description.

        Looks for common patterns like:
        - Questions? Contact: email@company.com
        - For inquiries: email@company.com
        - Contact us at email@company.com
        """
        patterns = [
            # Email anywhere in description
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                email = match.group(1)
                return email.lower().strip()

        return None
