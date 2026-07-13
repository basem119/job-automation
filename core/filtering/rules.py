from __future__ import annotations

import json

from config.preferences import Preferences
from core.filtering.recommendation_result import RuleResult, RecommendationDetail
from domain.job import Job


class HardRejectRule:
    """Immediately reject jobs for internships, trainees, etc."""
    
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        """Hard reject if title contains internship/trainee/volunteer keywords."""
        title = (job.title or "").strip().lower()
        hard_reject_keywords = [value.lower() for value in self.preferences.title.hard_reject]

        found_keywords = [keyword for keyword in hard_reject_keywords if keyword in title]
        if found_keywords:
            return RuleResult(
                passed=False,
                score=0,
                summary=f"Hard rejected: Title contains {', '.join(found_keywords)}",
                details=[RecommendationDetail("HardReject", 0, f"Found excluded keywords: {', '.join(found_keywords)}")],
            )

        return RuleResult(passed=True, score=0, summary="", details=[])


class LocationRule:
    """Score based on location preference."""
    REMOTE_SCORE = 15
    PREFERRED_LOCATION_SCORE = 10
    OTHER_COUNTRY_PENALTY = -5

    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        location = (job.location or "").strip().lower()
        
        # Check hard reject locations
        hard_reject = [value.lower() for value in self.preferences.location.hard_reject]
        if any(keyword in location for keyword in hard_reject):
            return RuleResult(
                passed=False,
                score=0,
                summary=f"Hard rejected: Location '{job.location}' is impossible",
                details=[RecommendationDetail("Location", 0, f"Hard rejected location: {job.location}")],
            )

        # Score based on preference
        details = []
        score = 0
        reason = ""

        preferred = [value.lower() for value in self.preferences.location.preferred]
        acceptable = [value.lower() for value in self.preferences.location.acceptable_countries]

        # Check if remote
        if any(pref in location for pref in preferred):
            score = self.REMOTE_SCORE
            reason = "Remote position (preferred)"
            details.append(RecommendationDetail("Location", score, reason))
        # Check if in acceptable countries
        elif any(country in location for country in acceptable):
            score = self.PREFERRED_LOCATION_SCORE
            reason = "Location in acceptable countries"
            details.append(RecommendationDetail("Location", score, reason))
        # Other locations get a small penalty
        else:
            score = self.OTHER_COUNTRY_PENALTY
            reason = "Location outside preferred region"
            details.append(RecommendationDetail("Location", score, reason))

        summary = f"Location scored {score}: {reason}"
        return RuleResult(passed=True, score=score, summary=summary, details=details)


class TitleRule:
    """Score based on title match - most important rule."""
    PRIMARY_TITLE_SCORE = 40
    SECONDARY_TITLE_SCORE = 25
    UNKNOWN_TITLE_SCORE = 5

    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        title = (job.title or "").strip().lower()
        
        if not title:
            return RuleResult(
                passed=True,
                score=0,
                summary="No title match (empty title)",
                details=[RecommendationDetail("Title", 0, "Job title is missing")]
            )

        primary = [value.lower() for value in self.preferences.title.primary]
        secondary = [value.lower() for value in self.preferences.title.secondary]
        
        details = []
        
        # Check primary titles first
        primary_match = [keyword for keyword in primary if keyword in title]
        if primary_match:
            details.append(RecommendationDetail("Title", self.PRIMARY_TITLE_SCORE, f"Primary title matched: {', '.join(primary_match)}"))
            return RuleResult(
                passed=True,
                score=self.PRIMARY_TITLE_SCORE,
                summary=f"Excellent title match: {', '.join(primary_match)}",
                details=details
            )

        # Check secondary titles
        secondary_match = [keyword for keyword in secondary if keyword in title]
        if secondary_match:
            details.append(RecommendationDetail("Title", self.SECONDARY_TITLE_SCORE, f"Secondary title matched: {', '.join(secondary_match)}"))
            return RuleResult(
                passed=True,
                score=self.SECONDARY_TITLE_SCORE,
                summary=f"Good title match: {', '.join(secondary_match)}",
                details=details
            )

        # Unknown title gets a small score
        details.append(RecommendationDetail("Title", self.UNKNOWN_TITLE_SCORE, "Unknown title pattern"))
        return RuleResult(
            passed=True,
            score=self.UNKNOWN_TITLE_SCORE,
            summary="Title does not match known patterns",
            details=details
        )


class TechnologyRule:
    """Score based on required and preferred technologies."""
    REQUIRED_TECHNOLOGY_SCORE = 30
    PREFERRED_TECHNOLOGY_SCORE = 10
    MISSING_REQUIRED_PENALTY = -20
    MAX_PREFERRED_BONUS = 30

    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        technologies = {str(value).strip().lower() for value in (job.technologies or [])}
        required = {value.lower() for value in self.preferences.technologies.required}
        preferred = {value.lower() for value in self.preferences.technologies.preferred}

        details = []
        score = 0

        # Check required technologies
        required_match = required.intersection(technologies)
        if required_match:
            score += self.REQUIRED_TECHNOLOGY_SCORE
            details.append(RecommendationDetail(
                "Technology",
                self.REQUIRED_TECHNOLOGY_SCORE,
                f"Has required tech(s): {', '.join(sorted(required_match))}"
            ))
        else:
            # Penalty for missing required tech
            score += self.MISSING_REQUIRED_PENALTY
            details.append(RecommendationDetail(
                "Technology",
                self.MISSING_REQUIRED_PENALTY,
                "Missing required technologies"
            ))

        # Check preferred technologies
        preferred_match = preferred.intersection(technologies)
        if preferred_match:
            # Cap the preferred bonus at MAX_PREFERRED_BONUS
            preferred_score = min(len(preferred_match) * self.PREFERRED_TECHNOLOGY_SCORE, self.MAX_PREFERRED_BONUS)
            score += preferred_score
            details.append(RecommendationDetail(
                "Technology",
                preferred_score,
                f"Has preferred tech(s): {', '.join(sorted(preferred_match))}"
            ))

        summary = f"Technology score: {score}"
        if required_match:
            summary += f". Has required: {', '.join(sorted(required_match))}"
        if preferred_match:
            summary += f". Has preferred: {', '.join(sorted(preferred_match))}"

        return RuleResult(
            passed=True,
            score=score,
            summary=summary,
            details=details
        )


class ExperienceRule:
    """Score based on experience keywords."""
    EXPERIENCE_KEYWORD_SCORE = 5

    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> RuleResult:
        text = " ".join(
            [
                (job.title or "").strip().lower(),
                (job.description or "").strip().lower(),
            ]
        )
        positive_keywords = [value.lower() for value in self.preferences.experience.positive]

        found_keywords = [keyword for keyword in positive_keywords if keyword in text]
        
        details = []
        if found_keywords:
            score = len(found_keywords) * self.EXPERIENCE_KEYWORD_SCORE
            details.append(RecommendationDetail(
                "Experience",
                score,
                f"Mentions: {', '.join(found_keywords)}"
            ))
            summary = f"Experience keywords found: {', '.join(found_keywords)}"
        else:
            score = 0
            summary = "No experience keywords mentioned"
            details.append(RecommendationDetail("Experience", 0, "No experience keywords found"))

        return RuleResult(
            passed=True,
            score=score,
            summary=summary,
            details=details
        )

