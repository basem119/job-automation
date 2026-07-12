from __future__ import annotations

from abc import ABC, abstractmethod

from domain.job import Job


class Collector(ABC):
    """Base interface for all job collectors."""

    name: str = "collector"

    @abstractmethod
    def collect(self) -> list[Job]:
        """Fetch and normalize jobs from one source."""


class CollectorRegistry:
    """Simple in-memory registry for collecting all configured collectors."""

    def __init__(self) -> None:
        self._collectors: dict[str, Collector] = {}

    def register(self, name: str, collector: Collector) -> None:
        self._collectors[name] = collector

    @property
    def collectors(self) -> list[Collector]:
        return list(self._collectors.values())
