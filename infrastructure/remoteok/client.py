from __future__ import annotations

from typing import Any

from infrastructure.http_client import HttpClient


class RemoteOkClient:
    """Small wrapper for the public RemoteOK API."""

    def __init__(self, http_client: HttpClient | None = None, endpoint: str = "https://remoteok.com/api") -> None:
        self.http_client = http_client or HttpClient()
        self.endpoint = endpoint

    def fetch_jobs(self) -> list[dict[str, Any]]:
        return self.http_client.get_json(self.endpoint)
