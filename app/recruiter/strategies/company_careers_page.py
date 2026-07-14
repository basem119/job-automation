"""Company careers page recruiter discovery strategy."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.recruiter.base import DiscoveryStrategy
from app.recruiter.models import RecruiterContact

if TYPE_CHECKING:
    from domain.job import Job


class CompanyCareersPageStrategy(DiscoveryStrategy):
    """Extract recruiter contact from company careers page."""

    @property
    def name(self) -> str:
        return "company_careers_page"

    def discover(self, job: Job) -> RecruiterContact | None:
        """Attempt to find recruiter email on company careers page.

        Derives careers page URL from:
        - Job URL (e.g., company.com/careers/job-id -> company.com/careers)
        - Company domain + common paths

        Args:
            job: Job to discover recruiter for

        Returns:
            RecruiterContact if found, None otherwise
        """
        if not job.url or not job.company:
            return None

        # Try to extract company domain from job URL
        domain = self._extract_domain(job.url)
        if not domain:
            return None

        # Look for email pattern in job description that might be careers contact
        email = self._extract_careers_email(job.description or "")
        if email:
            return RecruiterContact(
                email=email,
                name=f"{job.company} Careers Team",
                source="company_careers_page",
                confidence=70,
            )

        return None

    def _extract_domain(self, url: str) -> str | None:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            return domain.lower() if domain else None
        except Exception:
            return None

    def _extract_careers_email(self, description: str) -> str | None:
        """Extract careers team email from job description.

        Looks for patterns like:
        - careers@company.com
        - jobs@company.com (in context of careers)
        - talent@company.com
        - For careers: careers@company.com
        """
        patterns = [
            # careers, jobs, talent, recruiting email addresses
            r"([a-zA-Z0-9._%+-]*(?:careers|jobs|talent|recruiting)[\w.-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            # Email after "careers" keyword
            r"(?:careers|for\s+careers)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                email = match.group(1)
                if email and "@" in email:
                    return email.lower().strip()

        return None
