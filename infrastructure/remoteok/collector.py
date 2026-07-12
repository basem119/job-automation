from __future__ import annotations

from domain.job import Job
from infrastructure.remoteok.client import RemoteOkClient
from infrastructure.remoteok.parser import RemoteOkParser


class RemoteOkCollector:
    """RemoteOK collector responsible only for download and parse orchestration."""

    def __init__(self, client: RemoteOkClient | None = None, parser: RemoteOkParser | None = None) -> None:
        self.client = client or RemoteOkClient()
        self.parser = parser or RemoteOkParser()

    def collect(self) -> list[Job]:
        payload = self.client.fetch_jobs()
        return self.parser.parse(payload)
