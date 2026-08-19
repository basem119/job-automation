from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from config.settings import Settings
from core.exceptions import ApplicationError, ConfigurationError
from domain.job import Job
from infrastructure.adzuna.client import AdzunaClient
from infrastructure.adzuna.collector import AdzunaCollector
from infrastructure.adzuna.parser import AdzunaParser
from infrastructure.collectors.collector import CollectionResult, Collector
from infrastructure.greenhouse.collector import GreenhouseCollector
from infrastructure.jobicy.client import JobicyClient
from infrastructure.jobicy.collector import JobicyCollector
from infrastructure.jobicy.parser import JobicyParser
from infrastructure.remoteok.collector import RemoteOkCollector
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository
from workflows.job_collection_workflow import JobCollectionWorkflow, build_collectors


class ExistingCollectorsStillWorkTests(unittest.TestCase):
    def test_remoteok_collector_returns_collection_result(self) -> None:
        client = Mock()
        parser = Mock()
        parser.parse_collection.return_value = CollectionResult(
            jobs=[
                Job(
                    id="r-1",
                    title="Backend Engineer",
                    company="Example",
                    location="Remote",
                    description="Build APIs",
                    url="https://example.com/r-1",
                    source="remoteok",
                )
            ],
            failed_records=0,
        )
        client.fetch_jobs.return_value = [{"id": 1}]

        collector = RemoteOkCollector(client=client, parser=parser)
        result = collector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].source, "remoteok")

    def test_greenhouse_collector_returns_collection_result(self) -> None:
        client = Mock()
        parser = Mock()
        parser.parse_collection.return_value = CollectionResult(
            jobs=[
                Job(
                    id="g-1",
                    title="Engineer",
                    company="Example",
                    location="Remote",
                    description="Build",
                    url="https://example.com/g-1",
                    source="greenhouse",
                )
            ],
            failed_records=0,
        )
        client.fetch_jobs.return_value = [{"id": 1}]

        collector = GreenhouseCollector(client=client, parser=parser)
        result = collector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].source, "greenhouse")


class AdzunaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = AdzunaParser()

    def test_valid_response_with_multiple_jobs(self) -> None:
        payload = [
            {
                "id": "a-1",
                "title": "Senior Python Engineer",
                "company": {"display_name": "Acme"},
                "location": {"display_name": "London"},
                "redirect_url": "https://example.com/a-1",
                "description": "Build systems",
                "created": "2026-08-01T10:00:00Z",
            },
            {
                "id": "a-2",
                "title": "Platform Engineer",
                "company": {"display_name": "Globex"},
                "location": {"area": ["UK", "England", "Remote"]},
                "redirect_url": "https://example.com/a-2",
                "description": "Operate platform",
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 2)
        self.assertEqual(result.failed_records, 0)
        self.assertEqual(result.jobs[0].source, "adzuna")

    def test_malformed_record_is_skipped(self) -> None:
        payload = [
            {
                "id": "a-1",
                "title": "Senior Python Engineer",
                "company": {"display_name": "Acme"},
                "location": {"display_name": "Remote"},
                "redirect_url": "https://example.com/a-1",
            },
            {
                "id": "a-2",
                "company": {"display_name": "Broken"},
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.failed_records, 1)

    def test_missing_required_fields_are_skipped(self) -> None:
        payload = [{"id": "a-1", "title": "Engineer"}]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 0)
        self.assertEqual(result.failed_records, 1)

    def test_empty_response(self) -> None:
        result = self.parser.parse_collection([])

        self.assertEqual(len(result.jobs), 0)
        self.assertEqual(result.failed_records, 0)


class AdzunaClientCollectorTests(unittest.TestCase):
    def test_missing_configuration_raises(self) -> None:
        client = AdzunaClient(app_id="", app_key="", country="us", http_client=Mock())

        with self.assertRaises(ConfigurationError):
            client.fetch_jobs()

    def test_http_error_timeout_network_invalid_json_surface_as_application_error(self) -> None:
        for message in [
            "Timeout while requesting Adzuna jobs API",
            "Network error while requesting Adzuna jobs API",
            "Invalid JSON response from Adzuna jobs API",
        ]:
            http_client = Mock()
            http_client.get_json.side_effect = ApplicationError(message)
            client = AdzunaClient(app_id="id", app_key="key", country="us", http_client=http_client)
            collector = AdzunaCollector(client=client)

            with self.assertRaises(ApplicationError):
                collector.collect()

    def test_invalid_payload_raises(self) -> None:
        http_client = Mock()
        http_client.get_json.return_value = {"unexpected": []}
        client = AdzunaClient(app_id="id", app_key="key", country="us", http_client=http_client)

        with self.assertRaises(ApplicationError):
            client.fetch_jobs()


class JobicyParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = JobicyParser()

    def test_valid_response_with_multiple_jobs(self) -> None:
        payload = [
            {
                "id": "j-1",
                "jobTitle": "Backend Engineer",
                "companyName": "Acme",
                "jobGeo": "Remote",
                "url": "https://example.com/j-1",
                "jobDescription": "Build APIs",
                "pubDate": "2026-08-01T11:00:00Z",
            },
            {
                "id": "j-2",
                "title": "Platform Engineer",
                "company": {"name": "Globex"},
                "location": "Berlin",
                "jobUrl": "https://example.com/j-2",
                "description": "Operate systems",
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 2)
        self.assertEqual(result.failed_records, 0)
        self.assertEqual(result.jobs[0].source, "jobicy")

    def test_malformed_record_is_skipped(self) -> None:
        payload = [
            {
                "id": "j-1",
                "jobTitle": "Backend Engineer",
                "companyName": "Acme",
                "jobGeo": "Remote",
                "url": "https://example.com/j-1",
            },
            {
                "id": "j-2",
                "title": "Missing URL",
                "companyName": "Broken",
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.failed_records, 1)

    def test_empty_response(self) -> None:
        result = self.parser.parse_collection([])

        self.assertEqual(len(result.jobs), 0)
        self.assertEqual(result.failed_records, 0)


class JobicyClientCollectorTests(unittest.TestCase):
    def test_invalid_payload_raises(self) -> None:
        http_client = Mock()
        http_client.get_json.return_value = {"items": []}
        client = JobicyClient(http_client=http_client)

        with self.assertRaises(ApplicationError):
            client.fetch_jobs()

    def test_http_error_timeout_network_invalid_json_surface_as_application_error(self) -> None:
        for message in [
            "Timeout while requesting Jobicy jobs API",
            "Network error while requesting Jobicy jobs API",
            "Invalid JSON response from Jobicy jobs API",
        ]:
            http_client = Mock()
            http_client.get_json.side_effect = ApplicationError(message)
            collector = JobicyCollector(client=JobicyClient(http_client=http_client))

            with self.assertRaises(ApplicationError):
                collector.collect()

    def test_collector_disabled_via_settings(self) -> None:
        settings = Settings(
            env={
                "ENABLE_REMOTEOK": "false",
                "ENABLE_GREENHOUSE": "false",
                "ADZUNA_ENABLED": "false",
                "JOBICY_ENABLED": "false",
            }
        )

        collectors = build_collectors(settings)
        self.assertEqual(len(collectors), 4)
        disabled = [collector for collector in collectors if not getattr(collector, "enabled", True)]
        self.assertEqual(len(disabled), 4)


class SourceIsolationWorkflowTests(unittest.TestCase):
    class SuccessfulCollector(Collector):
        def __init__(self, name: str, jobs: list[Job], failed_records: int = 0) -> None:
            self.name = name
            self.jobs = jobs
            self.failed_records = failed_records

        def collect(self) -> CollectionResult:
            return CollectionResult(jobs=self.jobs, failed_records=self.failed_records)

    class FailingCollector(Collector):
        def __init__(self, name: str, error: Exception) -> None:
            self.name = name
            self.error = error

        def collect(self) -> CollectionResult:
            raise self.error

    @staticmethod
    def _job(job_id: str, source: str) -> Job:
        return Job(
            id=job_id,
            title="Engineer",
            company="Example",
            location="Remote",
            description="Build systems",
            url=f"https://example.com/{source}/{job_id}",
            source=source,
        )

    def test_workflow_continues_when_adzuna_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = SQLiteDatabase(Path(temp_dir) / "jobs.db")
            repository = JobRepository(db)

            workflow = JobCollectionWorkflow(
                collectors=[
                    self.SuccessfulCollector("RemoteOK", [self._job("r-1", "remoteok")]),
                    self.SuccessfulCollector("Greenhouse", [self._job("g-1", "greenhouse")]),
                    self.FailingCollector("Adzuna", ApplicationError("adzuna down")),
                    self.SuccessfulCollector("Jobicy", [self._job("j-1", "jobicy")]),
                ],
                repository=repository,
                database=db,
            )

            summary = workflow.run()

            self.assertEqual(summary["sources_attempted"], 4)
            self.assertEqual(summary["sources_succeeded"], 3)
            self.assertEqual(summary["sources_failed"], 1)
            self.assertEqual(summary["inserted"], 3)

            db.close()

    def test_workflow_continues_when_jobicy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = SQLiteDatabase(Path(temp_dir) / "jobs.db")
            repository = JobRepository(db)

            workflow = JobCollectionWorkflow(
                collectors=[
                    self.SuccessfulCollector("Adzuna", [self._job("a-1", "adzuna")]),
                    self.FailingCollector("Jobicy", ApplicationError("jobicy down")),
                ],
                repository=repository,
                database=db,
            )

            summary = workflow.run()

            self.assertEqual(summary["sources_attempted"], 2)
            self.assertEqual(summary["sources_succeeded"], 1)
            self.assertEqual(summary["sources_failed"], 1)
            self.assertEqual(summary["inserted"], 1)

            db.close()

    def test_workflow_completes_when_all_collectors_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = SQLiteDatabase(Path(temp_dir) / "jobs.db")
            repository = JobRepository(db)

            workflow = JobCollectionWorkflow(
                collectors=[
                    self.FailingCollector("RemoteOK", ApplicationError("remote down")),
                    self.FailingCollector("Greenhouse", ApplicationError("greenhouse down")),
                    self.FailingCollector("Adzuna", ApplicationError("adzuna down")),
                    self.FailingCollector("Jobicy", ApplicationError("jobicy down")),
                ],
                repository=repository,
                database=db,
            )

            summary = workflow.run()

            self.assertEqual(summary["sources_attempted"], 4)
            self.assertEqual(summary["sources_succeeded"], 0)
            self.assertEqual(summary["sources_failed"], 4)
            self.assertEqual(summary["inserted"], 0)

            db.close()

    def test_malformed_record_does_not_stop_valid_jobs_from_same_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = SQLiteDatabase(Path(temp_dir) / "jobs.db")
            repository = JobRepository(db)

            workflow = JobCollectionWorkflow(
                collectors=[
                    self.SuccessfulCollector(
                        "Adzuna",
                        [self._job("a-1", "adzuna")],
                        failed_records=1,
                    )
                ],
                repository=repository,
                database=db,
            )

            summary = workflow.run()

            self.assertEqual(summary["inserted"], 1)
            self.assertEqual(summary["failed"], 1)
            self.assertEqual(summary["collector_stats"][0]["failed"], 1)

            db.close()


if __name__ == "__main__":
    unittest.main()
