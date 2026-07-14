"""Recruiter discovery data models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecruiterContact:
    """Represents a discovered recruiter contact."""

    email: str
    name: str
    source: str
    confidence: int

    def __post_init__(self) -> None:
        """Validate fields."""
        if not self.email or "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email}")
        if not self.source:
            raise ValueError("Source cannot be empty")
        if not 0 <= self.confidence <= 100:
            raise ValueError(f"Confidence must be 0-100, got {self.confidence}")
