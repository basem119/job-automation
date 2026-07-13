from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecommendationDetail:
    """Individual rule contribution to recommendation score."""
    rule: str
    score: int
    reason: str


@dataclass
class RuleResult:
    """Result from a recommendation rule evaluation."""
    passed: bool  # False for hard rejection
    score: int  # Contribution to total score
    summary: str  # Human-readable explanation
    details: list[RecommendationDetail] = field(default_factory=list)
