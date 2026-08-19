from __future__ import annotations

from infrastructure.adzuna.client import AdzunaClient
from infrastructure.adzuna.parser import AdzunaParser
from infrastructure.collectors.collector import CollectionResult, Collector


class AdzunaCollector(Collector):
    """Adzuna collector responsible only for fetch and parse orchestration."""

    name = "Adzuna"

    def __init__(self, client: AdzunaClient, parser: AdzunaParser | None = None) -> None:
        self.client = client
        self.parser = parser or AdzunaParser()

    def collect(self) -> CollectionResult:
        payload = self.client.fetch_jobs()
        return self.parser.parse_collection(payload)
