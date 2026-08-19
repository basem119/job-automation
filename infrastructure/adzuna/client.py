from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from core.exceptions import ApplicationError, ConfigurationError
from infrastructure.http_client import HttpClient


class AdzunaClient:
    """Client for the official Adzuna jobs API."""

    def __init__(
        self,
        app_id: str,
        app_key: str,
        country: str = "us",
        http_client: HttpClient | None = None,
        endpoint: str = "https://api.adzuna.com/v1/api/jobs",
    ) -> None:
        self.http_client = http_client or HttpClient(timeout=15)
        self.app_id = app_id.strip()
        self.app_key = app_key.strip()
        self.country = country.strip().lower() or "us"
        self.endpoint = endpoint.rstrip("/")

    def fetch_jobs(self) -> list[dict[str, Any]]:
        self._validate_configuration()

        query = urlencode(
            {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "results_per_page": 50,
                "content-type": "application/json",
            }
        )
        url = f"{self.endpoint}/{self.country}/search/1?{query}"
        payload = self.http_client.get_json(url, error_context="Adzuna jobs API")

        if not isinstance(payload, dict):
            raise ApplicationError("Unexpected Adzuna payload format")

        results = payload.get("results")
        if not isinstance(results, list):
            raise ApplicationError("Adzuna payload missing results list")

        return results

    def _validate_configuration(self) -> None:
        missing: list[str] = []

        if not self.app_id:
            missing.append("ADZUNA_APP_ID")
        if not self.app_key:
            missing.append("ADZUNA_APP_KEY")
        if not self.country:
            missing.append("ADZUNA_COUNTRY")

        if missing:
            raise ConfigurationError(
                f"Adzuna collector is enabled but missing required configuration: {', '.join(missing)}"
            )
