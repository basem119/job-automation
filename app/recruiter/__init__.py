"""Recruiter discovery package."""
from __future__ import annotations

from app.recruiter.base import DiscoveryStrategy
from app.recruiter.models import RecruiterContact
from app.recruiter.service import RecruiterDiscoveryService

__all__ = [
    "RecruiterContact",
    "DiscoveryStrategy",
    "RecruiterDiscoveryService",
]
