"""Company contact page recruiter discovery strategy."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.recruiter.base import DiscoveryStrategy
from app.recruiter.models import RecruiterContact

if TYPE_CHECKING:
    from domain.job import Job


class CompanyContactPageStrategy(DiscoveryStrategy):
    """Extract recruiter contact from company contact page."""

    @property
    def name(self) -> str:
        return "company_contact_page"

    def discover(self, job: Job) -> RecruiterContact | None:
        """Attempt to find recruiter email on company contact page.

        Looks for hiring or recruitment-related email addresses in:
        - Job description
        - Company metadata

        Args:
            job: Job to discover recruiter for

        Returns:
            RecruiterContact if found, None otherwise
        """
        if not job.description:
            return None

        # Look for hiring/recruiting specific email patterns
        email = self._extract_hiring_email(job.description)
        if email:
            return RecruiterContact(
                email=email,
                name=f"{job.company} Hiring Team",
                source="company_contact_page",
                confidence=65,
            )

        return None

    def _extract_hiring_email(self, description: str) -> str | None:
        """Extract hiring/recruitment email from description.

        Looks for patterns like:
        - hiring@company.com
        - recruiting@company.com
        - recruitment@company.com
        - hr-contact@company.com
        """
        patterns = [
            r"(?:hiring|recruitment|recruiting|hr-contact|hr_contact)\s*[:=]?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            r"([a-zA-Z0-9._%+-]*(?:hiring|recruitment|recruiting|hr)[\w.-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                email = match.group(1) if "@" in match.group(1) else match.group(0)
                return email.lower().strip()

        return None
