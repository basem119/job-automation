from __future__ import annotations

from typing import Any

import requests

from core.exceptions import ApplicationError


class HttpClient:
    """Small, reusable HTTP client wrapper around the requests library."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def get_json(self, url: str) -> Any:
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise ApplicationError(f"Timeout while requesting {url}") from exc
        except requests.exceptions.RequestException as exc:
            raise ApplicationError(f"Network error while requesting {url}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApplicationError(f"Invalid JSON response from {url}") from exc

        return payload
