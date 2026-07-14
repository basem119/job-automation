"""Base class for recruiter discovery strategies."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.job import Job

from app.recruiter.models import RecruiterContact


class DiscoveryStrategy(ABC):
    """Base class for recruiter discovery strategies."""

    @abstractmethod
    def discover(self, job: Job) -> RecruiterContact | None:
        """Attempt to discover recruiter contact for a job.

        Args:
            job: Job to discover recruiter for

        Returns:
            RecruiterContact if successful, None otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging."""
        pass
