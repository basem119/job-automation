from __future__ import annotations

from typing import Any

from core.exceptions import ApplicationError
from infrastructure.http_client import HttpClient


class JobicyClient:
    """Client for Jobicy public jobs feed/API."""

    def __init__(
        self,
        http_client: HttpClient | None = None,
        endpoint: str = "https://jobicy.com/api/v2/remote-jobs",
    ) -> None:
        self.http_client = http_client or HttpClient(timeout=15)
        self.endpoint = endpoint

    def fetch_jobs(self) -> list[dict[str, Any]]:
        payload = self.http_client.get_json(self.endpoint, error_context="Jobicy jobs API")

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if isinstance(payload, dict):
            for key in ("jobs", "data", "results"):
                jobs = payload.get(key)
                if isinstance(jobs, list):
                    return [item for item in jobs if isinstance(item, dict)]

        raise ApplicationError("Unexpected Jobicy payload format")
