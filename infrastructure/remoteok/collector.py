from __future__ import annotations

from infrastructure.collectors.collector import CollectionResult, Collector
from infrastructure.remoteok.client import RemoteOkClient
from infrastructure.remoteok.parser import RemoteOkParser


class RemoteOkCollector(Collector):
    """RemoteOK collector responsible only for download and parse orchestration."""

    name = "RemoteOK"

    def __init__(self, client: RemoteOkClient | None = None, parser: RemoteOkParser | None = None) -> None:
        self.client = client or RemoteOkClient()
        self.parser = parser or RemoteOkParser()

    def collect(self) -> CollectionResult:
        payload = self.client.fetch_jobs()
        return self.parser.parse_collection(payload)
