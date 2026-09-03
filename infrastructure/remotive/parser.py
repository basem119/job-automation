from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from domain.job import Job
from infrastructure.collectors.collector import CollectionResult

logger = logging.getLogger("job_automation")


class RemotiveParser:
    """Convert Remotive payload records into generic Job objects."""

    def parse(self, payload: list[dict[str, Any]]) -> list[Job]:
        return self.parse_collection(payload).jobs

    def parse_collection(self, payload: list[dict[str, Any]]) -> CollectionResult:
        jobs: list[Job] = []
        failed_records = 0

        for item in payload:
            try:
                job = self._parse_record(item)
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring malformed Remotive record: %s", exc)
                failed_records += 1
                continue

            jobs.append(job)

        return CollectionResult(jobs=jobs, failed_records=failed_records)

    def _parse_record(self, item: dict[str, Any]) -> Job:
        if not isinstance(item, dict):
            raise ValueError("Expected a dictionary record")

        title = self._normalize_text(item.get("title"))
        company = self._normalize_text(item.get("company_name"))
        location = self._normalize_text(item.get("candidate_required_location") or item.get("location"))
        url = self._normalize_text(item.get("url"))
        description = self._normalize_text(item.get("description") or "")

        if not title or not company or not location or not url:
            raise ValueError("Missing required job fields")

        published_at = self._parse_published_at(item.get("publication_date"))

        tags = item.get("tags")
        technologies = self._normalize_tags(tags)

        return Job(
            id=str(item.get("id") or url),
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source="remotive",
            published_at=published_at,
            salary=self._normalize_text(item.get("salary")) or None,
            technologies=technologies,
            normalized_location=self._normalize_location(location),
            description_text=self._normalize_text(description),
        )

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value in (None, ""):
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_tags(value: Any) -> list[str] | None:
        if value is None:
            return None

        if isinstance(value, list):
            cleaned = [str(tag).strip() for tag in value if str(tag).strip()]
            return cleaned or None

        text = str(value).strip()
        if not text:
            return None

        return [text]

    @staticmethod
    def _normalize_location(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _parse_published_at(value: Any) -> datetime | None:
        if value in (None, ""):
            return None

        normalized = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
