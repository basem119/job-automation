"""Recruiter discovery service."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.recruiter.base import DiscoveryStrategy
from app.recruiter.models import RecruiterContact
from app.recruiter.strategies import (
    CommonAddressStrategy,
    CompanyCareersPageStrategy,
    CompanyContactPageStrategy,
    GreenhouseStrategy,
)

if TYPE_CHECKING:
    from domain.job import Job

logger = logging.getLogger("job_automation")


class RecruiterDiscoveryService:
    """Service to discover recruiter contacts using discovery strategies.

    Executes strategies sequentially until one succeeds.
    """

    def __init__(self, strategies: list[DiscoveryStrategy] | None = None) -> None:
        """Initialize service with strategies.

        If no strategies provided, uses default order:
        1. Greenhouse (highest priority, highest confidence)
        2. Company Careers Page
        3. Company Contact Page
        4. Common Address (lowest priority, lowest confidence)

        Args:
            strategies: Optional list of strategies to use. If None, uses defaults.
        """
        if strategies is None:
            strategies = [
                GreenhouseStrategy(),
                CompanyCareersPageStrategy(),
                CompanyContactPageStrategy(),
                CommonAddressStrategy(),
            ]

        self.strategies = strategies

    def discover(self, job: Job) -> RecruiterContact | None:
        """Discover recruiter contact for a job.

        Executes strategies sequentially and returns after first success.

        Args:
            job: Job to discover recruiter for

        Returns:
            RecruiterContact if found, None if no strategy succeeded
        """
        for strategy in self.strategies:
            try:
                contact = strategy.discover(job)
                if contact:
                    logger.debug(
                        f"Recruiter discovered: {contact.email} "
                        f"(strategy={strategy.name}, confidence={contact.confidence})"
                    )
                    return contact
            except Exception as e:
                logger.warning(
                    f"Strategy {strategy.name} failed: {e}",
                    exc_info=True,
                )

        logger.debug(f"No recruiter found for job {job.id}")
        return None
