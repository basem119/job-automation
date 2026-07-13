from __future__ import annotations

from config.preferences import Preferences
from core.filtering.result import RuleResult
from domain.job import Job


class LocationRule:
    PREFERRED_LOCATION_SCORE = 10

    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        location = (job.location or "").strip().lower()
        allowed = {value.lower() for value in self.preferences.location.allowed}
        rejected = {value.lower() for value in self.preferences.location.rejected}

        if not location:
            return RuleResult(passed=False, score=0, reason="Job location is missing")

        if location in rejected:
            return RuleResult(passed=False, score=0, reason=f"Location '{job.location}' is on rejected list")

        if allowed and location not in allowed:
            return RuleResult(passed=False, score=0, reason=f"Location '{job.location}' is not in allowed list")

        # Job location is acceptable, award points
        return RuleResult(
            passed=True,
            score=self.PREFERRED_LOCATION_SCORE,
            reason=f"Location '{job.location}' is acceptable",
        )


class TitleRule:
    TITLE_SCORE = 30

    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        title = (job.title or "").strip().lower()
        required = [value.lower() for value in self.preferences.title.required]

        if not title:
            return RuleResult(passed=False, score=0, reason="Job title is missing")

        matched_keywords = [keyword for keyword in required if keyword in title]
        if not matched_keywords:
            return RuleResult(passed=False, score=0, reason=f"Title '{job.title}' does not contain required keywords")

        return RuleResult(
            passed=True,
            score=self.TITLE_SCORE,
            reason=f"Title contains required keyword(s): {', '.join(matched_keywords)}",
        )


class TechnologyRule:
    REQUIRED_TECHNOLOGY_SCORE = 40
    PREFERRED_TECHNOLOGY_SCORE = 20

    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        technologies = {str(value).strip().lower() for value in (job.technologies or [])}
        required = {value.lower() for value in self.preferences.technologies.required}
        preferred = {value.lower() for value in getattr(self.preferences.technologies, 'preferred', [])}

        if not required:
            return RuleResult(passed=True, score=0, reason="No required technologies configured")

        # Check if job has at least one required technology
        required_match = required.intersection(technologies)
        if not required_match:
            return RuleResult(
                passed=False,
                score=0,
                reason="Job does not have any required technologies",
            )

        # Calculate score
        score = self.REQUIRED_TECHNOLOGY_SCORE
        reasons = [f"Has required tech(s): {', '.join(sorted(required_match))}"]

        # Award bonus points for preferred technologies
        preferred_match = preferred.intersection(technologies)
        if preferred_match:
            score += self.PREFERRED_TECHNOLOGY_SCORE
            reasons.append(f"Has preferred tech(s): {', '.join(sorted(preferred_match))}")

        return RuleResult(passed=True, score=score, reason=" + ".join(reasons))


class ExcludedKeywordRule:
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        text = " ".join(
            [
                (job.title or "").strip().lower(),
                (job.description or "").strip().lower(),
                (job.location or "").strip().lower(),
            ]
        )
        keywords = [value.lower() for value in self.preferences.excluded_keywords.keywords]

        found_keywords = [keyword for keyword in keywords if keyword in text]
        if found_keywords:
            return RuleResult(
                passed=False,
                score=0,
                reason=f"Job contains excluded keyword(s): {', '.join(found_keywords)}",
            )

        return RuleResult(passed=True, score=0, reason="No excluded keywords found")
