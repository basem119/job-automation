from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.job import Job


@dataclass
class CollectionResult:
    """Normalized output from a collector run."""

    jobs: list[Job]
    failed_records: int = 0


class Collector(ABC):
    """Base interface for all job collectors."""

    name: str = "collector"
    enabled: bool = True

    @abstractmethod
    def collect(self) -> CollectionResult | list[Job]:
        """Fetch and normalize jobs from one source."""


class DisabledCollector(Collector):
    """No-op collector used to report configured but disabled sources."""

    enabled = False

    def __init__(self, name: str) -> None:
        self.name = name

    def collect(self) -> CollectionResult:
        return CollectionResult(jobs=[], failed_records=0)


class CollectorRegistry:
    """Simple in-memory registry for collecting all configured collectors."""

    def __init__(self) -> None:
        self._collectors: dict[str, Collector] = {}

    def register(self, name: str, collector: Collector) -> None:
        self._collectors[name] = collector

    @property
    def collectors(self) -> list[Collector]:
        return list(self._collectors.values())
