from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class LocationPreferences:
    preferred: list[str]
    acceptable_countries: list[str]
    hard_reject: list[str]


@dataclass
class TitlePreferences:
    primary: list[str]
    secondary: list[str]
    hard_reject: list[str]


@dataclass
class ExperiencePreferences:
    positive: list[str]


@dataclass
class TechnologyPreferences:
    required: list[str]
    preferred: list[str]


@dataclass
class RecommendationPreferences:
    minimum_score: int


@dataclass
class Preferences:
    location: LocationPreferences
    title: TitlePreferences
    experience: ExperiencePreferences
    technologies: TechnologyPreferences
    recommendation: RecommendationPreferences

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Preferences":
        preferences_path = Path(path or Path(__file__).resolve().with_name("preferences.yaml"))
        with preferences_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        return cls(
            location=LocationPreferences(
                preferred=[str(value).strip().lower() for value in payload.get("location", {}).get("preferred", [])],
                acceptable_countries=[str(value).strip().lower() for value in payload.get("location", {}).get("acceptable_countries", [])],
                hard_reject=[str(value).strip().lower() for value in payload.get("location", {}).get("hard_reject", [])],
            ),
            title=TitlePreferences(
                primary=[str(value).strip().lower() for value in payload.get("title", {}).get("primary", [])],
                secondary=[str(value).strip().lower() for value in payload.get("title", {}).get("secondary", [])],
                hard_reject=[str(value).strip().lower() for value in payload.get("title", {}).get("hard_reject", [])],
            ),
            experience=ExperiencePreferences(
                positive=[str(value).strip().lower() for value in payload.get("experience", {}).get("positive", [])],
            ),
            technologies=TechnologyPreferences(
                required=[str(value).strip().lower() for value in payload.get("technologies", {}).get("required", [])],
                preferred=[str(value).strip().lower() for value in payload.get("technologies", {}).get("preferred", [])],
            ),
            recommendation=RecommendationPreferences(
                minimum_score=int(payload.get("recommendation", {}).get("minimum_score", 70)),
            ),
        )
