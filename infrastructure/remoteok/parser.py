from __future__ import annotations

import logging
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

        title = item.get("position") or item.get("title")
        company = item.get("company") or item.get("company_name")
        location = item.get("location") or item.get("geo")
        url = item.get("url") or item.get("apply_url")
        description = item.get("description") or item.get("snippet") or ""

        if not title or not company or not location or not url:
            raise ValueError("Missing required job fields")

        technologies = item.get("tags") or item.get("technologies") or []
        if not isinstance(technologies, list):
            technologies = [str(technologies)]

        published_at = self._parse_published_at(item.get("date") or item.get("published_at"))

        return Job(
            id=str(item.get("id") or url),
            title=str(title),
            company=str(company),
            location=str(location),
            description=str(description),
            url=str(url),
            source="remoteok",
            published_at=published_at,
            salary=item.get("salary"),
            technologies=[str(value) for value in technologies],
        )

    @staticmethod
    def _parse_published_at(value: Any) -> datetime | None:
        if value in (None, ""):
            return None

        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
