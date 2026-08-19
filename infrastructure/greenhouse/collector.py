from __future__ import annotations

from infrastructure.collectors.collector import CollectionResult, Collector
from infrastructure.greenhouse.client import GreenhouseClient
from infrastructure.greenhouse.parser import GreenhouseParser


class GreenhouseCollector(Collector):
    """Greenhouse collector responsible only for fetch and parse orchestration."""

    name = "Greenhouse"

    def __init__(
        self,
        client: GreenhouseClient | None = None,
        parser: GreenhouseParser | None = None,
    ) -> None:
        self.client = client or GreenhouseClient()
        self.parser = parser or GreenhouseParser()

    def collect(self) -> CollectionResult:
        payload = self.client.fetch_jobs()
        return self.parser.parse_collection(payload)
