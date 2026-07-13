from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.preferences import Preferences
from core.filtering.engine import FilteringEngine
from core.filtering.result import RuleResult
from core.filtering.rules import ExcludedKeywordRule, LocationRule, TechnologyRule, TitleRule
from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository


class RuleResultTests(unittest.TestCase):
    def test_rule_result_stores_decision_and_score(self) -> None:
        result = RuleResult(passed=True, score=30, reason="Test reason")

        self.assertTrue(result.passed)
        self.assertEqual(result.score, 30)
        self.assertEqual(result.reason, "Test reason")

    def test_rule_result_rejection(self) -> None:
        result = RuleResult(passed=False, score=0, reason="Rejected due to test")

        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.reason, "Rejected due to test")


class LocationRuleScoreTests(unittest.TestCase):
    def test_location_rule_awards_points_for_acceptable_location(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = LocationRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)

        self.assertTrue(result.passed)
        self.assertEqual(result.score, LocationRule.PREFERRED_LOCATION_SCORE)
        self.assertIn("acceptable", result.reason.lower())

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
        self.assertIn("rejected list", result.reason.lower())


class TitleRuleScoreTests(unittest.TestCase):
    def test_title_rule_awards_points_for_matching_title(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TitleRule(preferences)
        job = Job(
            id="job-1",
            title="Senior Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)

        self.assertTrue(result.passed)
        self.assertEqual(result.score, TitleRule.TITLE_SCORE)
        self.assertIn("required keyword", result.reason.lower())

    def test_title_rule_rejects_non_matching_title(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TitleRule(preferences)
        job = Job(
            id="job-1",
            title="Product Manager",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)

        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0)


class TechnologyRuleScoreTests(unittest.TestCase):
    def test_technology_rule_awards_required_technology_points(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TechnologyRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
            technologies=["c#", "sql server"],
        )

        result = rule.evaluate(job)

        self.assertTrue(result.passed)
        self.assertEqual(result.score, TechnologyRule.REQUIRED_TECHNOLOGY_SCORE)

    def test_technology_rule_awards_bonus_for_preferred_technologies(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TechnologyRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
            technologies=["c#", "sql server", "docker", "kubernetes"],
        )

        result = rule.evaluate(job)

        self.assertTrue(result.passed)
        expected_score = TechnologyRule.REQUIRED_TECHNOLOGY_SCORE + TechnologyRule.PREFERRED_TECHNOLOGY_SCORE
        self.assertEqual(result.score, expected_score)

    def test_technology_rule_rejects_missing_required_technologies(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TechnologyRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
            technologies=["python", "django"],
        )

        result = rule.evaluate(job)

        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0)


class ExcludedKeywordRuleTests(unittest.TestCase):
    def test_excluded_keyword_rule_passes_without_keywords(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = ExcludedKeywordRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Build scalable APIs",
            url="https://example.com/jobs/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)

        self.assertTrue(result.passed)
        self.assertEqual(result.score, 0)


class ScoreAccumulationTests(unittest.TestCase):
    def test_engine_accumulates_scores_from_multiple_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = FilteringEngine(database=database, repository=repository, preferences=preferences)

            job = Job(
                id="job-1",
                title="Senior Backend Engineer",
                company="Example",
                location="Remote",
                description="Build scalable APIs with C#",
                url="https://example.com/jobs/1",
                source="remoteok",
                status="NEW",
                technologies=["c#", "sql server", "docker"],
            )

            repository.insert_jobs([job])
            summary = engine.run()

            self.assertEqual(summary["evaluated"], 1)
            self.assertEqual(summary["filtered"], 1)
            self.assertEqual(summary["rejected"], 0)
            self.assertGreater(summary["average_score"], 0)
            self.assertEqual(summary["highest_score"], summary["average_score"])

            # Verify score is stored in database
            score_row = database.connection.execute(
                "SELECT score FROM jobs WHERE job_id = ?",
                ("job-1",),
            ).fetchone()
            self.assertGreater(score_row["score"], 0)

            database.close()


class RejectionLogicTests(unittest.TestCase):
    def test_engine_rejects_job_and_sets_zero_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = FilteringEngine(database=database, repository=repository, preferences=preferences)

            job = Job(
                id="job-1",
                title="Product Manager",
                company="Example",
                location="onsite only",
                description="Non-technical role",
                url="https://example.com/jobs/1",
                source="remoteok",
                status="NEW",
                technologies=["product"],
            )

            repository.insert_jobs([job])
            summary = engine.run()

            self.assertEqual(summary["evaluated"], 1)
            self.assertEqual(summary["filtered"], 0)
            self.assertEqual(summary["rejected"], 1)

            # Verify rejection is stored
            job_row = database.connection.execute(
                "SELECT status, score FROM jobs WHERE job_id = ?",
                ("job-1",),
            ).fetchone()
            self.assertEqual(job_row["status"], "REJECTED")
            self.assertEqual(job_row["score"], 0)

            database.close()


class RepositoryUpdateTests(unittest.TestCase):
    def test_repository_updates_job_result_atomically(self) -> None:
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
                status="NEW",
            )

            repository.insert_jobs([job])
            repository.update_job_result("job-1", "FILTERED", 85, "Test reason")

            result_row = database.connection.execute(
                "SELECT status, score, filter_reason FROM jobs WHERE job_id = ?",
                ("job-1",),
            ).fetchone()

            self.assertEqual(result_row["status"], "FILTERED")
            self.assertEqual(result_row["score"], 85)
            self.assertEqual(result_row["filter_reason"], "Test reason")

            database.close()


class SummaryStatisticsTests(unittest.TestCase):
    def test_engine_calculates_score_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = FilteringEngine(database=database, repository=repository, preferences=preferences)

            jobs = [
                Job(
                    id="job-1",
                    title="Senior Backend Engineer",
                    company="Example",
                    location="Remote",
                    description="Build APIs with C#",
                    url="https://example.com/jobs/1",
                    source="remoteok",
                    status="NEW",
                    technologies=["c#", "sql server", "docker"],
                ),
                Job(
                    id="job-2",
                    title="Backend Engineer",
                    company="Example",
                    location="Remote",
                    description="Build APIs",
                    url="https://example.com/jobs/2",
                    source="remoteok",
                    status="NEW",
                    technologies=["c#", "sql server"],
                ),
            ]

            repository.insert_jobs(jobs)
            summary = engine.run()

            self.assertEqual(summary["evaluated"], 2)
            self.assertEqual(summary["filtered"], 2)
            self.assertGreater(summary["average_score"], 0)
            self.assertGreaterEqual(summary["highest_score"], summary["average_score"])
            self.assertLessEqual(summary["lowest_score"], summary["average_score"])

            database.close()


if __name__ == "__main__":
    unittest.main()
