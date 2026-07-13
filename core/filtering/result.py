from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuleResult:
    """Result of evaluating a single rule against a job."""

    passed: bool
    score: int
    reason: str
