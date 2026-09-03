from __future__ import annotations

from infrastructure.collectors.collector import CollectionResult, Collector
from infrastructure.remotive.client import RemotiveClient
from infrastructure.remotive.parser import RemotiveParser


class RemotiveCollector(Collector):
    """Remotive collector responsible only for fetch and parse orchestration."""

    name = "Remotive"

    def __init__(self, client: RemotiveClient | None = None, parser: RemotiveParser | None = None) -> None:
        self.client = client or RemotiveClient()
        self.parser = parser or RemotiveParser()

    def collect(self) -> CollectionResult:
        payload = self.client.fetch_jobs()
        return self.parser.parse_collection(payload)
