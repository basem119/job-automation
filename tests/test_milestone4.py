from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from domain.job import Job
from infrastructure.collectors.collector import Collector, CollectorRegistry
from infrastructure.greenhouse.collector import GreenhouseCollector
from infrastructure.greenhouse.client import GreenhouseClient
from infrastructure.greenhouse.parser import GreenhouseParser
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository
from workflows.job_collection_workflow import JobCollectionWorkflow


class DummyCollector(Collector):
    def __init__(self, name: str, jobs: list[Job]) -> None:
        self.name = name
        self._jobs = jobs

    def collect(self) -> list[Job]:
        return self._jobs


class CollectorInterfaceTests(unittest.TestCase):
    def test_collector_interface_requires_collect_implementation(self) -> None:
        with self.assertRaises(TypeError):
            Collector()


class CollectorRegistrationTests(unittest.TestCase):
    def test_registry_registers_collectors(self) -> None:
        registry = CollectorRegistry()
        first = DummyCollector("remoteok", [])
        second = DummyCollector("greenhouse", [])

        registry.register("remoteok", first)
        registry.register("greenhouse", second)

        collectors = registry.collectors
        self.assertEqual(len(collectors), 2)
        self.assertEqual([collector.name for collector in collectors], ["remoteok", "greenhouse"])


class WorkflowMultiCollectorTests(unittest.TestCase):
    def test_workflow_executes_multiple_collectors_and_summarizes_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)

            shared_job = Job(
                id="job-1",
                title="Backend Engineer",
                company="Example",
                location="Remote",
                description="Build APIs",
                url="https://example.com/jobs/1",
                source="remoteok",
            )
            unique_job = Job(
                id="job-2",
                title="Platform Engineer",
                company="Example",
                location="Remote",
                description="Run infrastructure",
                url="https://example.com/jobs/2",
                source="greenhouse",
            )

            workflow = JobCollectionWorkflow(
                collectors=[
                    DummyCollector("RemoteOK", [shared_job]),
                    DummyCollector("Greenhouse", [shared_job, unique_job]),
                ],
                repository=repository,
                database=database,
            )

            summary = workflow.run()

            self.assertEqual(summary["downloaded"], 3)
            self.assertEqual(summary["inserted"], 2)
            self.assertEqual(summary["duplicates"], 1)
            self.assertEqual(len(summary["collector_stats"]), 2)
            self.assertEqual(summary["collector_stats"][0]["name"], "RemoteOK")
            self.assertEqual(summary["collector_stats"][1]["name"], "Greenhouse")

            database.close()


class GreenhouseParserTests(unittest.TestCase):
    def test_parser_normalizes_greenhouse_job_payload(self) -> None:
        parser = GreenhouseParser()
        payload = [
            {
                "id": 42,
                "title": " Senior Software Engineer ",
                "location": {"name": " São Paulo, Brazil "},
                "absolute_url": " https://example.com/jobs/42 ",
                "content": "<p>Build APIs</p>",
                "updated_at": "2026-07-01T10:00:00+00:00",
                "company": {"name": "Example"},
            }
        ]

        jobs = parser.parse(payload)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "greenhouse")
        self.assertEqual(jobs[0].title, "Senior Software Engineer")
        self.assertEqual(jobs[0].company, "Example")
        self.assertEqual(jobs[0].normalized_location, "São Paulo, Brazil")
        self.assertEqual(jobs[0].description_text, "Build APIs")


class GreenhouseCollectorTests(unittest.TestCase):
    def test_collector_returns_parsed_jobs_for_greenhouse(self) -> None:
        client = Mock()
        parser = GreenhouseParser()
        client.fetch_jobs.return_value = [
            {
                "id": 7,
                "title": "Engineer",
                "location": {"name": "Remote"},
                "absolute_url": "https://example.com/jobs/7",
                "content": "Build things",
                "updated_at": "2026-07-01T10:00:00+00:00",
                "company": {"name": "Example"},
            }
        ]

        collector = GreenhouseCollector(client=client, parser=parser)
        jobs = collector.collect()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "greenhouse")
        self.assertEqual(jobs[0].title, "Engineer")


class GreenhouseHttpClientTests(unittest.TestCase):
    def test_greenhouse_client_fetches_jobs_from_public_api(self) -> None:
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = [
                {
                    "id": 11,
                    "title": "Engineer",
                    "location": {"name": "Remote"},
                    "absolute_url": "https://example.com/jobs/11",
                    "content": "Build things",
                    "updated_at": "2026-07-01T10:00:00+00:00",
                    "company": {"name": "Example"},
                }
            ]
            mock_get.return_value = mock_response

            client = GreenhouseClient(endpoint="https://example.com/jobs")
            jobs = client.fetch_jobs()

            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["title"], "Engineer")


if __name__ == "__main__":
    unittest.main()
