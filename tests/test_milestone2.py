from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from domain.job import Job
from infrastructure.remoteok.parser import RemoteOkParser
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository
from workflows.job_collection_workflow import JobCollectionWorkflow


class JobModelTests(unittest.TestCase):
    def test_job_model_accepts_basic_fields(self) -> None:
        job = Job(
            id="1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            published_at=datetime(2026, 7, 1),
            salary="$120k",
            technologies=["C#", ".NET"],
        )

        self.assertEqual(job.title, "Backend Engineer")
        self.assertEqual(job.company, "Example")
        self.assertEqual(job.source, "remoteok")


class ParserTests(unittest.TestCase):
    def test_parser_handles_valid_and_malformed_records(self) -> None:
        parser = RemoteOkParser()
        payload = [
            {
                "id": 1,
                "position": "Backend Engineer",
                "company": "Example",
                "location": "Remote",
                "url": "https://example.com/jobs/1",
                "description": "Build APIs",
                "date": "2026-07-01T10:00:00+00:00",
                "tags": ["C#", ".NET"],
            },
            {
                "id": 2,
                "company": "Broken",
            },
        ]

        jobs = parser.parse(payload)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Backend Engineer")


class RepositoryTests(unittest.TestCase):
    def test_repository_inserts_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)

            jobs = [
                Job(
                    id="job-1",
                    title="Backend Engineer",
                    company="Example",
                    location="Remote",
                    description="Build APIs",
                    url="https://example.com/jobs/1",
                    source="remoteok",
                )
            ]

            inserted = repository.insert_jobs(jobs)
            self.assertEqual(inserted["inserted"], 1)
            self.assertEqual(inserted["duplicates"], 0)

            database.close()


class WorkflowTests(unittest.TestCase):
    def test_workflow_run_returns_summary(self) -> None:
        class FakeCollector:
            def collect(self) -> list[Job]:
                return [
                    Job(
                        id="job-1",
                        title="Backend Engineer",
                        company="Example",
                        location="Remote",
                        description="Build APIs",
                        url="https://example.com/jobs/1",
                        source="remoteok",
                    )
                ]

        class FakeRepository:
            def insert_jobs(self, jobs: list[Job]) -> dict[str, int]:
                return {"inserted": len(jobs), "duplicates": 0, "total": len(jobs)}

        db_path = Path("tests/test_workflow.db")
        if db_path.exists():
            db_path.unlink()

        database = SQLiteDatabase(db_path)
        workflow = JobCollectionWorkflow(
            collector=FakeCollector(),
            repository=FakeRepository(),
            database=database,
        )
        stats = workflow.run()

        self.assertEqual(stats["downloaded"], 1)
        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(stats["duplicates"], 0)

        database.close()
        db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
