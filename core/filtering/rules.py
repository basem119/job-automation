from __future__ import annotations

from config.preferences import Preferences
from domain.job import Job


class LocationRule:
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> bool:
        location = (job.location or "").strip().lower()
        allowed = {value.lower() for value in self.preferences.location.allowed}
        rejected = {value.lower() for value in self.preferences.location.rejected}

        if not location:
            return False

        if location in rejected:
            return False

        if allowed and location not in allowed:
            return False

        return True


class TitleRule:
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> bool:
        title = (job.title or "").strip().lower()
        required = [value.lower() for value in self.preferences.title.required]

        if not title:
            return False

        return any(keyword in title for keyword in required)


class TechnologyRule:
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> bool:
        technologies = {str(value).strip().lower() for value in (job.technologies or [])}
        required = {value.lower() for value in self.preferences.technologies.required}

        if not required:
            return True

        # Job must have at least one of the required technologies
        return bool(required.intersection(technologies))


class ExcludedKeywordRule:
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences

    def evaluate(self, job: Job) -> bool:
        text = " ".join(
            [
                (job.title or "").strip().lower(),
                (job.description or "").strip().lower(),
                (job.location or "").strip().lower(),
            ]
        )
        keywords = [value.lower() for value in self.preferences.excluded_keywords.keywords]

        return not any(keyword in text for keyword in keywords)
