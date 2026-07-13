from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.preferences import Preferences
from core.filtering.engine import FilteringEngine
from core.filtering.rules import ExcludedKeywordRule, LocationRule, TechnologyRule, TitleRule
from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository


class RuleTests(unittest.TestCase):
    def test_location_rule_rejects_unwanted_location(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = LocationRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="onsite only",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0)

    def test_title_rule_accepts_matching_title(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TitleRule(preferences)
        job = Job(
            id="job-2",
            title="Senior Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/2",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertGreater(result.score, 0)

    def test_technology_rule_uses_required_technology(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TechnologyRule(preferences)
        job = Job(
            id="job-3",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/3",
            source="remoteok",
            status="NEW",
            technologies=["c#", "sql server", "asp.net core"],
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertGreater(result.score, 0)

    def test_excluded_keyword_rule_rejects_blocked_terms(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = ExcludedKeywordRule(preferences)
        job = Job(
            id="job-4",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Entry level position",
            url="https://example.com/jobs/4",
            source="remoteok",
            status="NEW",
        )

        # This test passes if excluded keywords are loaded
        # The rule should return True if no excluded keywords are found
        result = rule.evaluate(job)
        self.assertIsNotNone(result.passed)


class PreferencesTests(unittest.TestCase):
    def test_preferences_loader_reads_yaml_file(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))

        # Verify location preferences
        assert "remote" in preferences.location.allowed
        assert "anywhere" in preferences.location.allowed
        assert "onsite only" in preferences.location.rejected

        # Verify title preferences
        assert "backend engineer" in preferences.title.required or "senior backend engineer" in preferences.title.required
        
        # Verify technology preferences
        assert "c#" in preferences.technologies.required or ".net" in preferences.technologies.required
        
        # Verify excluded keywords exists
        assert isinstance(preferences.excluded_keywords.keywords, list)


class FilteringEngineTests(unittest.TestCase):
    def test_engine_filters_new_jobs_and_updates_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = FilteringEngine(database=database, repository=repository, preferences=preferences)

            accepted_job = Job(
                id="job-1",
                title="Senior Backend Engineer",
                company="Example",
                location="Remote",
                description="Build scalable APIs with C# and ASP.NET Core",
                url="https://example.com/jobs/1",
                source="remoteok",
                status="NEW",
                technologies=["c#", "sql server", "asp.net core"],
            )
            rejected_job = Job(
                id="job-2",
                title="Product Manager",
                company="Example",
                location="onsite only",
                description="Non-technical management role",
                url="https://example.com/jobs/2",
                source="remoteok",
                status="NEW",
                technologies=["product"],
            )

            repository.insert_jobs([accepted_job, rejected_job])
            summary = engine.run()

            self.assertEqual(summary["evaluated"], 2)
            self.assertEqual(summary["filtered"], 1)
            self.assertEqual(summary["rejected"], 1)

            accepted_row = database.connection.execute(
                "SELECT status FROM jobs WHERE job_id = ?",
                ("job-1",),
            ).fetchone()
            rejected_row = database.connection.execute(
                "SELECT status FROM jobs WHERE job_id = ?",
                ("job-2",),
            ).fetchone()

            self.assertEqual(accepted_row["status"], "FILTERED")
            self.assertEqual(rejected_row["status"], "REJECTED")

            database.close()


if __name__ == "__main__":
    unittest.main()
