from __future__ import annotations

from infrastructure.collectors.collector import CollectionResult, Collector
from infrastructure.jobicy.client import JobicyClient
from infrastructure.jobicy.parser import JobicyParser


class JobicyCollector(Collector):
    """Jobicy collector responsible only for fetch and parse orchestration."""

    name = "Jobicy"

    def __init__(self, client: JobicyClient | None = None, parser: JobicyParser | None = None) -> None:
        self.client = client or JobicyClient()
        self.parser = parser or JobicyParser()

    def collect(self) -> CollectionResult:
        payload = self.client.fetch_jobs()
        return self.parser.parse_collection(payload)
