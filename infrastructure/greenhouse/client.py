from __future__ import annotations

from typing import Any

from core.exceptions import ApplicationError
from infrastructure.http_client import HttpClient


class GreenhouseClient:
    """Client for the public Greenhouse job board API."""

    def __init__(
        self,
        http_client: HttpClient | None = None,
        endpoint: str = "https://boards-api.greenhouse.io/v1/boards/greenhouse/jobs",
    ) -> None:
        self.http_client = http_client or HttpClient()
        self.endpoint = endpoint

    def fetch_jobs(self) -> list[dict[str, Any]]:
        all_jobs: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        page = 1

        while True:
            page_url = self._build_page_url(page)
            payload = self.http_client.get_json(page_url)
            jobs = self._extract_jobs(payload)

            if not jobs:
                break

            new_jobs: list[dict[str, Any]] = []
            for job in jobs:
                if not isinstance(job, dict):
                    continue

                job_id = str(job.get("id") or job.get("absolute_url") or job.get("title") or "")
                if job_id in seen_ids:
                    continue

                seen_ids.add(job_id)
                new_jobs.append(job)

            if not new_jobs:
                break

            all_jobs.extend(new_jobs)

            meta = payload.get("meta") if isinstance(payload, dict) else {}
            total = meta.get("total") if isinstance(meta, dict) else None
            if isinstance(total, int) and len(all_jobs) >= total:
                break

            page += 1

        return all_jobs

    def _build_page_url(self, page: int) -> str:
        separator = "&" if "?" in self.endpoint else "?"
        return f"{self.endpoint}{separator}page={page}"

    @staticmethod
    def _extract_jobs(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            jobs = payload.get("jobs")
            if isinstance(jobs, list):
                return jobs

        raise ApplicationError(f"Unexpected Greenhouse payload format from endpoint")
