"""Result of job analysis by AI provider."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """AI analysis result for a recommended job."""

    job_id: str
    provider: str
    match_summary: str
    strengths: list[str]
    missing_skills: list[str]
    recommended_resume: str
    email_highlights: str
    confidence: int  # 0-100

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "job_id": self.job_id,
            "provider": self.provider,
            "match_summary": self.match_summary,
            "strengths": self.strengths,
            "missing_skills": self.missing_skills,
            "recommended_resume": self.recommended_resume,
            "email_highlights": self.email_highlights,
            "confidence": self.confidence,
        }
