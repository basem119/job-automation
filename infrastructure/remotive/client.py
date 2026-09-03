from __future__ import annotations

from typing import Any

from core.exceptions import ApplicationError
from infrastructure.http_client import HttpClient


class RemotiveClient:
    """Client for the public Remotive jobs API."""

    def __init__(
        self,
        http_client: HttpClient | None = None,
        endpoint: str = "https://remotive.com/api/remote-jobs",
    ) -> None:
        self.http_client = http_client or HttpClient(timeout=15)
        self.endpoint = endpoint

    def fetch_jobs(self) -> list[dict[str, Any]]:
        payload = self.http_client.get_json(self.endpoint, error_context="Remotive jobs API")

        if isinstance(payload, dict):
            jobs = payload.get("jobs")
            if isinstance(jobs, list):
                return [item for item in jobs if isinstance(item, dict)]

        raise ApplicationError("Unexpected Remotive payload format")
