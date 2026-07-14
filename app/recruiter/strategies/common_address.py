"""Common recruiting email address strategy."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.recruiter.base import DiscoveryStrategy
from app.recruiter.models import RecruiterContact

if TYPE_CHECKING:
    from domain.job import Job


class CommonAddressStrategy(DiscoveryStrategy):
    """Generate common recruiting email addresses from company domain."""

    COMMON_PREFIXES = ["careers", "jobs", "talent", "recruiting", "hr"]

    @property
    def name(self) -> str:
        return "common_address"

    def discover(self, job: Job) -> RecruiterContact | None:
        """Generate common recruiting email addresses.

        Creates addresses like:
        - careers@company.com
        - jobs@company.com
        - talent@company.com
        - recruiting@company.com
        - hr@company.com

        Args:
            job: Job to discover recruiter for

        Returns:
            RecruiterContact if domain is known, None otherwise
        """
        if not job.url:
            return None

        domain = self._extract_domain(job.url)
        if not domain or not domain.endswith((".com", ".io", ".org", ".net", ".co", ".uk")):
            return None

        # Generate first common address
        for prefix in self.COMMON_PREFIXES:
            email = f"{prefix}@{domain}"
            return RecruiterContact(
                email=email,
                name=f"{job.company} {prefix.title()} Team",
                source="common_address",
                confidence=40,  # Lower confidence for generated addresses
            )

        return None

    def _extract_domain(self, url: str) -> str | None:
        """Extract domain from URL.

        Handles patterns like:
        - company.com/careers/job
        - company.greenhouse.io
        - company.lever.co
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]

            if not domain:
                return None

            domain = domain.lower()

            # Remove common job board subdomains
            for job_board in ["greenhouse.io", "lever.co", "workable.com", "smartrecruiters.com"]:
                if domain.endswith(job_board):
                    return domain

            # Extract main domain
            parts = domain.split(".")
            if len(parts) >= 2:
                # Return last two parts (company.com)
                return ".".join(parts[-2:])

            return domain
        except Exception:
            return None
