from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class LocationPreferences:
    allowed: list[str]
    rejected: list[str]


@dataclass
class TitlePreferences:
    required: list[str]


@dataclass
class TechnologyPreferences:
    required: list[str]
    preferred: list[str] = None

    def __post_init__(self) -> None:
        if self.preferred is None:
            self.preferred = []


@dataclass
class ExcludedKeywordPreferences:
    keywords: list[str]


@dataclass
class Preferences:
    location: LocationPreferences
    title: TitlePreferences
    technologies: TechnologyPreferences
    excluded_keywords: ExcludedKeywordPreferences

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Preferences":
        preferences_path = Path(path or Path(__file__).resolve().with_name("preferences.yaml"))
        with preferences_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        return cls(
            location=LocationPreferences(
                allowed=[str(value).strip().lower() for value in payload.get("location", {}).get("allowed", [])],
                rejected=[str(value).strip().lower() for value in payload.get("location", {}).get("rejected", [])],
            ),
            title=TitlePreferences(
                required=[str(value).strip().lower() for value in payload.get("title", {}).get("required", [])],
            ),
            technologies=TechnologyPreferences(
                required=[str(value).strip().lower() for value in payload.get("technologies", {}).get("required", [])],
                preferred=[str(value).strip().lower() for value in payload.get("technologies", {}).get("preferred", [])],
            ),
            excluded_keywords=ExcludedKeywordPreferences(
                keywords=[str(value).strip().lower() for value in payload.get("excluded_keywords", {}).get("keywords", [])],
            ),
        )
