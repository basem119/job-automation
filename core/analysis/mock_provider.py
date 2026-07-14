"""Mock AI provider for development without API costs."""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.analysis.analysis_result import AnalysisResult
from core.analysis.provider import AIProvider

if TYPE_CHECKING:
    from domain.job import Job


class MockProvider(AIProvider):
    """Mock provider that generates deterministic analysis.
    
    Returns realistic fake values using job data as seed.
    Allows development without API costs.
    """

    @property
    def name(self) -> str:
        """Provider name."""
        return "mock"

    def analyze(self, job: Job) -> AnalysisResult:
        """Generate deterministic mock analysis.
        
        Uses job data as seed to produce consistent results.
        
        Args:
            job: Recommended job to analyze
            
        Returns:
            AnalysisResult with mock data
        """
        # Use job id hash for deterministic randomness
        seed = int(hashlib.md5(job.id.encode()).hexdigest()[:8], 16)

        # Generate consistent but varied outputs
        strength_count = (seed % 3) + 3  # 3-5 strengths
        missing_count = (seed // 10 % 2) + 1  # 1-2 missing skills

        strengths = self._generate_strengths(job, strength_count)
        missing_skills = self._generate_missing_skills(job, missing_count)
        confidence = 70 + (seed % 25)  # 70-94

        match_summary = (
            f"Strong match for {job.title}. Your {self.profile.experience.years} years of "
            f"experience aligns well with requirements. "
            f"Excellent fit: {', '.join(strengths[:2])}."
        )

        primary_skills = self.profile.primary_skills()
        primary_str = ", ".join(primary_skills[:2]) if primary_skills else "technical expertise"
        
        recommended_resume = (
            f"Highlight: {primary_str} expertise. "
            f"Emphasize: {', '.join(strengths[:2])}. "
            f"For this role: leadership, system design, scalability."
        )

        primary_skill = primary_skills[0] if primary_skills else "technical"
        secondary_skills = ", ".join(primary_skills[1:3]) if len(primary_skills) > 1 else "modern technologies"
        
        email_highlights = (
            f"I'm excited about this {job.title} role at {job.company}. "
            f"My expertise in {primary_skill} and {secondary_skills} aligns with your requirements. "
            f"I bring {self.profile.experience.years}+ years of relevant experience in "
            f"{strengths[0].lower()}."
        )

        return AnalysisResult(
            job_id=job.id,
            provider=self.name,
            match_summary=match_summary,
            strengths=strengths,
            missing_skills=missing_skills,
            recommended_resume=recommended_resume,
            email_highlights=email_highlights,
            confidence=confidence,
        )

    def _generate_strengths(self, job: Job, count: int) -> list[str]:
        """Generate matching strengths."""
        description_lower = (job.description or "").lower()
        job_title_lower = (job.title or "").lower()

        default_strengths = [
            "backend architecture",
            "microservices design",
            "cloud platforms",
            "database optimization",
            "API development",
            "system scalability",
            "team leadership",
            "code quality",
        ]

        # Try to find tech-specific strengths
        strengths = []
        for skill in self.profile.skills.all_skills():
            if skill in description_lower or skill in job_title_lower:
                strengths.append(f"{skill} expertise")
                if len(strengths) >= count:
                    break

        # Fill with defaults if needed
        while len(strengths) < count:
            idx = len(strengths) % len(default_strengths)
            strength = default_strengths[idx]
            if strength not in strengths:
                strengths.append(strength)

        return strengths[:count]

    def _generate_missing_skills(self, job: Job, count: int) -> list[str]:
        """Generate missing skills."""
        description_lower = (job.description or "").lower()

        possible_missing = [
            "Kubernetes orchestration",
            "Machine learning basics",
            "GraphQL experience",
            "Event-driven architecture",
            "Terraform IaC",
            "gRPC services",
            "Load balancing strategies",
        ]

        missing = []
        for skill in possible_missing:
            skill_lower = skill.lower()
            # Only mark as missing if not in description and not in profile
            if (
                skill_lower not in description_lower
                and skill_lower not in " ".join(self.profile.skills.all_skills()).lower()
            ):
                missing.append(skill)
                if len(missing) >= count:
                    break

        return missing[:count] if missing else ["Advanced DevOps"]

    def __repr__(self) -> str:
        """String representation."""
        return f"MockProvider(profile={self.profile.name})"
