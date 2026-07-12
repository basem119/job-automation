from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from domain.job import Job
from infrastructure.remoteok.parser import RemoteOkParser
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository


class ParserNormalizationTests(unittest.TestCase):
    def test_parser_decodes_mojibake_and_normalizes_fields(self) -> None:
        parser = RemoteOkParser()
        payload = [
            {
                "id": 1,
                "position": " Backend Engineer ",
                "company": "Example",
                "location": "  SÃ£o Paulo  ",
                "url": " https://example.com/jobs/1 ",
                "description": " Build APIs ",
                "date": "2026-07-01T10:00:00+00:00",
            }
        ]

        jobs = parser.parse(payload)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Backend Engineer")
        self.assertEqual(jobs[0].normalized_location, "São Paulo")
        self.assertEqual(jobs[0].url, "https://example.com/jobs/1")
        self.assertEqual(jobs[0].description_text, "Build APIs")


class RepositoryDuplicateTests(unittest.TestCase):
    def test_repository_inserts_only_new_jobs_and_counts_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)

            job = Job(
                id="job-1",
                title="Backend Engineer",
                company="Example",
                location="Remote",
                description="Build APIs",
                url="https://example.com/jobs/1",
                source="remoteok",
            )

            first_result = repository.insert_jobs([job])
            second_result = repository.insert_jobs([job])

            self.assertEqual(first_result["inserted"], 1)
            self.assertEqual(first_result["duplicates"], 0)
            self.assertEqual(second_result["inserted"], 0)
            self.assertEqual(second_result["duplicates"], 1)
            self.assertEqual(second_result["total"], 1)

            database.close()


class HashGenerationTests(unittest.TestCase):
    def test_hash_generation_uses_source_and_job_id(self) -> None:
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
        )

        hash_value = JobRepository.build_hash(job)
        self.assertTrue(hash_value)
        self.assertEqual(len(hash_value), 64)


if __name__ == "__main__":
    unittest.main()
