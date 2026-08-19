from __future__ import annotations

import logging
import re
from datetime import datetime
from html import unescape
from typing import Any

from domain.job import Job
from infrastructure.collectors.collector import CollectionResult

logger = logging.getLogger("job_automation")


class GreenhouseParser:
    """Convert Greenhouse payload records into generic Job objects."""

    def parse(self, payload: list[dict[str, Any]] | dict[str, Any]) -> list[Job]:
        return self.parse_collection(payload).jobs

    def parse_collection(self, payload: list[dict[str, Any]] | dict[str, Any]) -> CollectionResult:
        jobs_payload = payload.get("jobs") if isinstance(payload, dict) else payload
        if not isinstance(jobs_payload, list):
            raise ValueError("Greenhouse payload must be a list or a dict with a jobs list")

        jobs: list[Job] = []
        failed_records = 0

        for item in jobs_payload:
            try:
                job = self._parse_record(item)
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring malformed Greenhouse record: %s", exc)
                failed_records += 1
                continue

            jobs.append(job)

        return CollectionResult(jobs=jobs, failed_records=failed_records)

    def _parse_record(self, item: dict[str, Any]) -> Job:
        if not isinstance(item, dict):
            raise ValueError("Expected a dictionary record")

        title = self._normalize_text(item.get("title"))
        company = self._normalize_text(item.get("company_name"))
        if not company and isinstance(item.get("company"), dict):
            company = self._normalize_text(item.get("company").get("name"))
        elif not company:
            company = self._normalize_text(item.get("company"))

        location = self._normalize_text((item.get("location") or {}).get("name")) if isinstance(item.get("location"), dict) else self._normalize_text(item.get("location"))
        url = self._normalize_url(item.get("absolute_url") or item.get("url"))
        description = self._normalize_text(self._strip_html(item.get("content") or item.get("description") or ""))

        if not title or not company or not location or not url:
            raise ValueError("Missing required job fields")

        published_at = self._parse_published_at(item.get("updated_at") or item.get("published_at"))

        return Job(
            id=str(item.get("id") or url),
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source="greenhouse",
            published_at=published_at,
            salary=self._normalize_text(item.get("salary")),
            technologies=None,
            normalized_location=self._normalize_location(location),
            description_text=description,
        )

    @staticmethod
    def _parse_published_at(value: Any) -> datetime | None:
        if value in (None, ""):
            return None

        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value in (None, ""):
            return ""

        text = unescape(str(value)).strip()
        if not text:
            return ""

        try:
            latin1_bytes = text.encode("latin-1")
            utf8_text = latin1_bytes.decode("utf-8")
            if utf8_text != text:
                return utf8_text
        except UnicodeError:
            pass

        return text

    @staticmethod
    def _normalize_url(value: Any) -> str:
        return GreenhouseParser._normalize_text(value).strip()

    @staticmethod
    def _normalize_location(value: str) -> str:
        text = GreenhouseParser._normalize_text(value)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _strip_html(value: Any) -> str:
        text = GreenhouseParser._normalize_text(value)
        return re.sub(r"<[^>]+>", " ", text)
