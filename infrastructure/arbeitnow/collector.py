from __future__ import annotations

from infrastructure.arbeitnow.client import ArbeitnowClient
from infrastructure.arbeitnow.parser import ArbeitnowParser
from infrastructure.collectors.collector import CollectionResult, Collector


class ArbeitnowCollector(Collector):
    """Arbeitnow collector responsible only for fetch and parse orchestration."""

    name = "Arbeitnow"

    def __init__(self, client: ArbeitnowClient | None = None, parser: ArbeitnowParser | None = None) -> None:
        self.client = client or ArbeitnowClient()
        self.parser = parser or ArbeitnowParser()

    def collect(self) -> CollectionResult:
        payload = self.client.fetch_jobs()
        return self.parser.parse_collection(payload)
