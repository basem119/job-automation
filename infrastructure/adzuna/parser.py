from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from domain.job import Job
from infrastructure.collectors.collector import CollectionResult

logger = logging.getLogger("job_automation")


class AdzunaParser:
    """Convert Adzuna payload records into generic Job objects."""

    def parse(self, payload: list[dict[str, Any]]) -> list[Job]:
        return self.parse_collection(payload).jobs

    def parse_collection(self, payload: list[dict[str, Any]]) -> CollectionResult:
        jobs: list[Job] = []
        failed_records = 0

        for item in payload:
            try:
                job = self._parse_record(item)
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring malformed Adzuna record: %s", exc)
                failed_records += 1
                continue

            jobs.append(job)

        return CollectionResult(jobs=jobs, failed_records=failed_records)

    def _parse_record(self, item: dict[str, Any]) -> Job:
        if not isinstance(item, dict):
            raise ValueError("Expected a dictionary record")

        title = self._normalize_text(item.get("title"))

        company = ""
        company_node = item.get("company")
        if isinstance(company_node, dict):
            company = self._normalize_text(company_node.get("display_name") or company_node.get("name"))
        else:
            company = self._normalize_text(company_node)

        location = self._normalize_location(item.get("location"))
        url = self._normalize_text(item.get("redirect_url") or item.get("url"))
        description = self._normalize_text(item.get("description") or "")

        if not title or not company or not location or not url:
            raise ValueError("Missing required job fields")

        published_at = self._parse_published_at(item.get("created") or item.get("published_at"))

        external_id = str(item.get("id") or item.get("adref") or url)

        return Job(
            id=external_id,
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source="adzuna",
            published_at=published_at,
            salary=self._normalize_salary(item.get("salary_min"), item.get("salary_max")),
            technologies=None,
            normalized_location=location,
            description_text=description,
        )

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value in (None, ""):
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_location(location_value: Any) -> str:
        if isinstance(location_value, dict):
            display_name = location_value.get("display_name")
            if display_name:
                return AdzunaParser._normalize_text(display_name)

            area = location_value.get("area")
            if isinstance(area, list):
                cleaned = [AdzunaParser._normalize_text(value) for value in area if value]
                return re.sub(r"\s+", " ", ", ".join(cleaned)).strip()

        return AdzunaParser._normalize_text(location_value)

    @staticmethod
    def _parse_published_at(value: Any) -> datetime | None:
        if value in (None, ""):
            return None

        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _normalize_salary(min_value: Any, max_value: Any) -> str | None:
        minimum = AdzunaParser._normalize_text(min_value)
        maximum = AdzunaParser._normalize_text(max_value)

        if not minimum and not maximum:
            return None
        if minimum and maximum:
            return f"{minimum} - {maximum}"

        return minimum or maximum
