from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from config.settings import Settings
from core.exceptions import ApplicationError
from domain.job import Job
from infrastructure.arbeitnow.client import ArbeitnowClient
from infrastructure.arbeitnow.collector import ArbeitnowCollector
from infrastructure.arbeitnow.parser import ArbeitnowParser
from infrastructure.collectors.collector import CollectionResult, Collector
from infrastructure.remotive.client import RemotiveClient
from infrastructure.remotive.collector import RemotiveCollector
from infrastructure.remotive.parser import RemotiveParser
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository
from workflows.job_collection_workflow import JobCollectionWorkflow, build_collectors


class RemotiveParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = RemotiveParser()

    def test_valid_response_with_multiple_jobs(self) -> None:
        payload = [
            {
                "id": 1001,
                "title": "Backend Engineer",
                "company_name": "Acme",
                "candidate_required_location": "Worldwide",
                "url": "https://remotive.com/jobs/1001",
                "description": "Build APIs",
                "publication_date": "2026-08-01T10:00:00",
                "salary": "$80k-$120k",
                "tags": ["python", "django"],
            },
            {
                "id": 1002,
                "title": "Frontend Developer",
                "company_name": "Globex",
                "candidate_required_location": "USA Only",
                "url": "https://remotive.com/jobs/1002",
                "description": "Build UIs",
                "tags": ["react"],
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 2)
        self.assertEqual(result.failed_records, 0)
        self.assertEqual(result.jobs[0].source, "remotive")
        self.assertEqual(result.jobs[0].company, "Acme")
        self.assertEqual(result.jobs[0].location, "Worldwide")
        self.assertEqual(result.jobs[0].technologies, ["python", "django"])

    def test_malformed_record_is_skipped(self) -> None:
        payload = [
            {
                "id": 1001,
                "title": "Backend Engineer",
                "company_name": "Acme",
                "candidate_required_location": "Remote",
                "url": "https://remotive.com/jobs/1001",
            },
            {
                "id": 1002,
                "title": "Missing Company",
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.failed_records, 1)

    def test_missing_required_fields_are_skipped(self) -> None:
        payload = [{"id": 1001, "title": "Engineer"}]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 0)
        self.assertEqual(result.failed_records, 1)

    def test_empty_response(self) -> None:
        result = self.parser.parse_collection([])

        self.assertEqual(len(result.jobs), 0)
        self.assertEqual(result.failed_records, 0)

    def test_published_at_parsed_correctly(self) -> None:
        payload = [
            {
                "id": 1001,
                "title": "Engineer",
                "company_name": "Acme",
                "candidate_required_location": "Remote",
                "url": "https://remotive.com/jobs/1001",
                "publication_date": "2026-08-15T14:30:00",
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertIsNotNone(result.jobs[0].published_at)


class RemotiveClientTests(unittest.TestCase):
    def test_valid_payload_extracts_jobs(self) -> None:
        http_client = Mock()
        http_client.get_json.return_value = {
            "jobs": [
                {"id": 1, "title": "Engineer"},
                {"id": 2, "title": "Designer"},
            ]
        }
        client = RemotiveClient(http_client=http_client)

        jobs = client.fetch_jobs()

        self.assertEqual(len(jobs), 2)

    def test_invalid_payload_raises(self) -> None:
        http_client = Mock()
        http_client.get_json.return_value = {"unexpected": []}
        client = RemotiveClient(http_client=http_client)

        with self.assertRaises(ApplicationError):
            client.fetch_jobs()

    def test_http_error_surfaces_as_application_error(self) -> None:
        http_client = Mock()
        http_client.get_json.side_effect = ApplicationError("Timeout while requesting Remotive jobs API")
        client = RemotiveClient(http_client=http_client)
        collector = RemotiveCollector(client=client)

        with self.assertRaises(ApplicationError):
            collector.collect()


class RemotiveCollectorTests(unittest.TestCase):
    def test_collector_returns_collection_result(self) -> None:
        client = Mock()
        parser = Mock()
        parser.parse_collection.return_value = CollectionResult(
            jobs=[
                Job(
                    id="rem-1",
                    title="Backend Engineer",
                    company="Acme",
                    location="Remote",
                    description="Build APIs",
                    url="https://remotive.com/jobs/rem-1",
                    source="remotive",
                )
            ],
            failed_records=0,
        )
        client.fetch_jobs.return_value = [{"id": 1}]

        collector = RemotiveCollector(client=client, parser=parser)
        result = collector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].source, "remotive")


class ArbeitnowParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ArbeitnowParser()

    def test_valid_response_with_multiple_jobs(self) -> None:
        payload = [
            {
                "slug": "backend-engineer-acme",
                "title": "Backend Engineer",
                "company_name": "Acme",
                "location": "Berlin",
                "url": "https://www.arbeitnow.com/view/backend-engineer-acme",
                "description": "Build APIs",
                "created_at": 1753990800,
                "tags": ["python", "fastapi"],
            },
            {
                "slug": "frontend-dev-globex",
                "title": "Frontend Developer",
                "company_name": "Globex",
                "location": "Remote",
                "url": "https://www.arbeitnow.com/view/frontend-dev-globex",
                "description": "Build UIs",
                "created_at": 1753904400,
                "tags": ["react"],
                "remote": True,
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 2)
        self.assertEqual(result.failed_records, 0)
        self.assertEqual(result.jobs[0].source, "arbeitnow")
        self.assertEqual(result.jobs[0].id, "backend-engineer-acme")
        self.assertEqual(result.jobs[0].technologies, ["python", "fastapi"])

    def test_remote_fallback_location(self) -> None:
        payload = [
            {
                "slug": "remote-job",
                "title": "Engineer",
                "company_name": "Acme",
                "location": "",
                "url": "https://www.arbeitnow.com/view/remote-job",
                "remote": True,
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].location, "Remote")

    def test_malformed_record_is_skipped(self) -> None:
        payload = [
            {
                "slug": "valid-job",
                "title": "Backend Engineer",
                "company_name": "Acme",
                "location": "Berlin",
                "url": "https://www.arbeitnow.com/view/valid-job",
            },
            {
                "slug": "broken-job",
                "title": "Missing Company",
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.failed_records, 1)

    def test_missing_required_fields_are_skipped(self) -> None:
        payload = [{"slug": "x", "title": "Engineer"}]

        result = self.parser.parse_collection(payload)

        self.assertEqual(len(result.jobs), 0)
        self.assertEqual(result.failed_records, 1)

    def test_empty_response(self) -> None:
        result = self.parser.parse_collection([])

        self.assertEqual(len(result.jobs), 0)
        self.assertEqual(result.failed_records, 0)

    def test_created_at_unix_timestamp_parsed_correctly(self) -> None:
        payload = [
            {
                "slug": "ts-job",
                "title": "Engineer",
                "company_name": "Acme",
                "location": "Remote",
                "url": "https://www.arbeitnow.com/view/ts-job",
                "created_at": 1753990800,
            },
        ]

        result = self.parser.parse_collection(payload)

        self.assertIsNotNone(result.jobs[0].published_at)
        self.assertEqual(result.jobs[0].published_at.tzinfo, timezone.utc)


class ArbeitnowClientTests(unittest.TestCase):
    def test_valid_payload_extracts_jobs(self) -> None:
        http_client = Mock()
        http_client.get_json.return_value = {
            "data": [
                {"slug": "job-1", "title": "Engineer"},
                {"slug": "job-2", "title": "Designer"},
            ],
            "links": {"next": None},
            "meta": {},
        }
        client = ArbeitnowClient(http_client=http_client, max_pages=1)

        jobs = client.fetch_jobs()

        self.assertEqual(len(jobs), 2)

    def test_pagination_stops_at_max_pages(self) -> None:
        http_client = Mock()

        def side_effect(url, error_context=None):
            return {
                "data": [{"slug": "job", "title": "Engineer"}],
                "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=99"},
                "meta": {},
            }

        http_client.get_json.side_effect = side_effect
        client = ArbeitnowClient(http_client=http_client, max_pages=2)

        jobs = client.fetch_jobs()

        self.assertEqual(http_client.get_json.call_count, 2)
        self.assertEqual(len(jobs), 2)

    def test_pagination_follows_next_url(self) -> None:
        http_client = Mock()
        responses = [
            {
                "data": [{"slug": "job-1", "title": "Engineer"}],
                "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=2"},
                "meta": {},
            },
            {
                "data": [{"slug": "job-2", "title": "Designer"}],
                "links": {"next": None},
                "meta": {},
            },
        ]
        http_client.get_json.side_effect = responses
        client = ArbeitnowClient(http_client=http_client, max_pages=5)

        jobs = client.fetch_jobs()

        self.assertEqual(len(jobs), 2)
        self.assertEqual(http_client.get_json.call_count, 2)
        http_client.get_json.assert_any_call(
            "https://www.arbeitnow.com/api/job-board-api?page=2",
            error_context="Arbeitnow jobs API",
        )

    def test_pagination_stops_when_no_next_link(self) -> None:
        http_client = Mock()
        http_client.get_json.return_value = {
            "data": [{"slug": "job", "title": "Engineer"}],
            "links": {"next": None},
            "meta": {},
        }
        client = ArbeitnowClient(http_client=http_client, max_pages=5)

        jobs = client.fetch_jobs()

        self.assertEqual(http_client.get_json.call_count, 1)

    def test_invalid_payload_raises(self) -> None:
        http_client = Mock()
        http_client.get_json.return_value = {"unexpected": []}
        client = ArbeitnowClient(http_client=http_client)

        with self.assertRaises(ApplicationError):
            client.fetch_jobs()

    def test_http_error_surfaces_as_application_error(self) -> None:
        http_client = Mock()
        http_client.get_json.side_effect = ApplicationError("Timeout while requesting Arbeitnow jobs API")
        client = ArbeitnowClient(http_client=http_client)
        collector = ArbeitnowCollector(client=client)

        with self.assertRaises(ApplicationError):
            collector.collect()


class ArbeitnowCollectorTests(unittest.TestCase):
    def test_collector_returns_collection_result(self) -> None:
        client = Mock()
        parser = Mock()
        parser.parse_collection.return_value = CollectionResult(
            jobs=[
                Job(
                    id="arb-1",
                    title="Backend Engineer",
                    company="Acme",
                    location="Berlin",
                    description="Build APIs",
                    url="https://www.arbeitnow.com/view/arb-1",
                    source="arbeitnow",
                )
            ],
            failed_records=0,
        )
        client.fetch_jobs.return_value = [{"slug": "arb-1"}]

        collector = ArbeitnowCollector(client=client, parser=parser)
        result = collector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].source, "arbeitnow")


class SettingsIntegrationTests(unittest.TestCase):
    def test_new_collectors_disabled_by_default(self) -> None:
        settings = Settings(
            env={
                "ENABLE_REMOTIVE": "false",
                "ENABLE_ARBEITNOW": "false",
            }
        )

        self.assertFalse(settings.enable_remotive)
        self.assertFalse(settings.enable_arbeitnow)

    def test_new_collectors_enabled_via_env(self) -> None:
        settings = Settings(
            env={
                "ENABLE_REMOTIVE": "true",
                "ENABLE_ARBEITNOW": "true",
            }
        )

        self.assertTrue(settings.enable_remotive)
        self.assertTrue(settings.enable_arbeitnow)

    def test_new_collectors_registered_in_build_collectors(self) -> None:
        settings = Settings(
            env={
                "ENABLE_REMOTEOK": "false",
                "ENABLE_GREENHOUSE": "false",
                "ADZUNA_ENABLED": "false",
                "JOBICY_ENABLED": "false",
                "ENABLE_REMOTIVE": "true",
                "ENABLE_ARBEITNOW": "true",
            }
        )

        collectors = build_collectors(settings)

        self.assertEqual(len(collectors), 6)
        names = [getattr(c, "name", "") for c in collectors]
        self.assertIn("Remotive", names)
        self.assertIn("Arbeitnow", names)

    def test_all_collectors_disabled(self) -> None:
        settings = Settings(
            env={
                "ENABLE_REMOTEOK": "false",
                "ENABLE_GREENHOUSE": "false",
                "ADZUNA_ENABLED": "false",
                "JOBICY_ENABLED": "false",
                "ENABLE_REMOTIVE": "false",
                "ENABLE_ARBEITNOW": "false",
            }
        )

        collectors = build_collectors(settings)
        disabled = [c for c in collectors if not getattr(c, "enabled", True)]
        self.assertEqual(len(disabled), 6)


class SourceIsolationTests(unittest.TestCase):
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

    def test_workflow_continues_when_remotive_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = SQLiteDatabase(Path(temp_dir) / "jobs.db")
            repository = JobRepository(db)

            workflow = JobCollectionWorkflow(
                collectors=[
                    self.SuccessfulCollector("RemoteOK", [self._job("r-1", "remoteok")]),
                    self.FailingCollector("Remotive", ApplicationError("remotive down")),
                    self.SuccessfulCollector("Arbeitnow", [self._job("an-1", "arbeitnow")]),
                ],
                repository=repository,
                database=db,
            )

            summary = workflow.run()

            self.assertEqual(summary["sources_attempted"], 3)
            self.assertEqual(summary["sources_succeeded"], 2)
            self.assertEqual(summary["sources_failed"], 1)
            self.assertEqual(summary["inserted"], 2)

            db.close()

    def test_workflow_continues_when_arbeitnow_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = SQLiteDatabase(Path(temp_dir) / "jobs.db")
            repository = JobRepository(db)

            workflow = JobCollectionWorkflow(
                collectors=[
                    self.SuccessfulCollector("Remotive", [self._job("rem-1", "remotive")]),
                    self.FailingCollector("Arbeitnow", ApplicationError("arbeitnow down")),
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


if __name__ == "__main__":
    unittest.main()
