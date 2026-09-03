from __future__ import annotations

import logging
from typing import Any

from core.exceptions import ApplicationError
from infrastructure.http_client import HttpClient

logger = logging.getLogger("job_automation")


class ArbeitnowClient:
    """Client for the public Arbeitnow jobs API with pagination support."""

    def __init__(
        self,
        http_client: HttpClient | None = None,
        endpoint: str = "https://www.arbeitnow.com/api/job-board-api",
        max_pages: int = 3,
    ) -> None:
        self.http_client = http_client or HttpClient(timeout=15)
        self.endpoint = endpoint
        self.max_pages = max_pages

    def fetch_jobs(self) -> list[dict[str, Any]]:
        all_jobs: list[dict[str, Any]] = []
        url: str | None = self.endpoint
        pages_fetched = 0

        while url and pages_fetched < self.max_pages:
            payload = self.http_client.get_json(url, error_context="Arbeitnow jobs API")
            pages_fetched += 1

            if not isinstance(payload, dict):
                raise ApplicationError("Unexpected Arbeitnow payload format")

            data = payload.get("data")
            if not isinstance(data, list):
                raise ApplicationError("Unexpected Arbeitnow payload format")

            jobs = [item for item in data if isinstance(item, dict)]
            all_jobs.extend(jobs)

            if not jobs:
                break

            links = payload.get("links", {})
            url = links.get("next") if isinstance(links, dict) else None

        logger.info("Arbeitnow: fetched %d jobs across %d page(s)", len(all_jobs), pages_fetched)
        return all_jobs
