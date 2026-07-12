from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from domain.job import Job

logger = logging.getLogger("job_automation")


class RemoteOkParser:
    """Convert RemoteOK payload records into generic Job objects."""

    def parse(self, payload: list[dict[str, Any]]) -> list[Job]:
        jobs: list[Job] = []

        for item in payload:
            try:
                job = self._parse_record(item)
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring malformed RemoteOK record: %s", exc)
                continue

            jobs.append(job)

        return jobs

    def _parse_record(self, item: dict[str, Any]) -> Job:
        if not isinstance(item, dict):
            raise ValueError("Expected a dictionary record")

        title = self._normalize_text(item.get("position") or item.get("title"))
        company = self._normalize_text(item.get("company") or item.get("company_name"))
        location = self._normalize_text(item.get("location") or item.get("geo"))
        url = self._normalize_url(item.get("url") or item.get("apply_url"))
        description = self._normalize_text(item.get("description") or item.get("snippet") or "")

        if not title or not company or not location or not url:
            raise ValueError("Missing required job fields")

        technologies = item.get("tags") or item.get("technologies") or []
        if not isinstance(technologies, list):
            technologies = [str(technologies)]

        published_at = self._parse_published_at(item.get("date") or item.get("published_at"))

        return Job(
            id=str(item.get("id") or url),
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source="remoteok",
            published_at=published_at,
            salary=self._normalize_text(item.get("salary")),
            technologies=[str(value) for value in technologies],
            normalized_location=self._normalize_location(location),
            description_text=self._normalize_text(description),
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

        text = str(value).strip()
        if not text:
            return ""

        try:
            latin1_bytes = text.encode("latin-1")
            utf8_text = latin1_bytes.decode("utf-8")
            if utf8_text != text:
                return utf8_text
        except UnicodeError:
            pass

        try:
            return text.encode("utf-8").decode("utf-8")
        except UnicodeError:
            return text

    @staticmethod
    def _normalize_url(value: Any) -> str:
        text = RemoteOkParser._normalize_text(value)
        return text.strip()

    @staticmethod
    def _normalize_location(value: str) -> str:
        text = RemoteOkParser._normalize_text(value)
        return re.sub(r"\s+", " ", text).strip()
