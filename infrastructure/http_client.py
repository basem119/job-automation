from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import requests

from core.exceptions import ApplicationError


class HttpClient:
    """Small, reusable HTTP client wrapper around the requests library."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def get_json(self, url: str, error_context: str | None = None) -> Any:
        context = error_context or self._safe_request_context(url)

        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise ApplicationError(f"Timeout while requesting {context}") from exc
        except requests.exceptions.RequestException as exc:
            raise ApplicationError(f"Network error while requesting {context}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApplicationError(f"Invalid JSON response from {context}") from exc

        return payload

    @staticmethod
    def _safe_request_context(url: str) -> str:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
