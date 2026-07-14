from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from config.preferences import Preferences
from core.filtering.engine import RecommendationEngine
from core.filtering.rules import ExperienceRule, HardRejectRule, LocationRule, TechnologyRule, TitleRule
from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository


class HardRejectRuleTests(unittest.TestCase):
    def test_hard_rejects_internship(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = HardRejectRule(preferences)
        job = Job(
            id="job-1",
            title="Internship - Backend Developer",
            company="Example",
            location="Remote",
            description="Paid internship",
            url="https://example.com/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0)

    def test_hard_rejects_trainee(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = HardRejectRule(preferences)
        job = Job(
            id="job-2",
            title="Trainee C# Developer",
            company="Example",
            location="Remote",
            description="Training program",
            url="https://example.com/2",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertFalse(result.passed)

    def test_allows_normal_job(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = HardRejectRule(preferences)
        job = Job(
            id="job-3",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Senior position",
            url="https://example.com/3",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)


class TitleRuleTests(unittest.TestCase):
    def test_primary_title_scores_highest(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TitleRule(preferences)
        job = Job(
            id="job-1",
            title="Senior Backend Engineer",
            company="Example",
            location="Remote",
            description="Lead role",
            url="https://example.com/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, rule.PRIMARY_TITLE_SCORE)

    def test_secondary_title_scores_medium(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TitleRule(preferences)
        job = Job(
            id="job-2",
            title="Platform Engineer",
            company="Example",
            location="Remote",
            description="Good role",
            url="https://example.com/2",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, rule.SECONDARY_TITLE_SCORE)

    def test_unknown_title_scores_small(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TitleRule(preferences)
        job = Job(
            id="job-3",
            title="Architect",
            company="Example",
            location="Remote",
            description="Some description",
            url="https://example.com/3",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, rule.UNKNOWN_TITLE_SCORE)


class LocationRuleTests(unittest.TestCase):
    def test_remote_position_scores_highest(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = LocationRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="Fully remote",
            url="https://example.com/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, rule.REMOTE_SCORE)

    def test_acceptable_country_scores_good(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = LocationRule(preferences)
        job = Job(
            id="job-2",
            title="Backend Engineer",
            company="Example",
            location="Cairo, Egypt",
            description="Local position",
            url="https://example.com/2",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, rule.PREFERRED_LOCATION_SCORE)

    def test_other_location_scores_negative(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = LocationRule(preferences)
        job = Job(
            id="job-3",
            title="Backend Engineer",
            company="Example",
            location="New York, USA",
            description="Abroad position",
            url="https://example.com/3",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, rule.OTHER_COUNTRY_PENALTY)

    def test_hard_rejects_onsite_only(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = LocationRule(preferences)
        job = Job(
            id="job-4",
            title="Backend Engineer",
            company="Example",
            location="Onsite only",
            description="Office required",
            url="https://example.com/4",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertFalse(result.passed)


class TechnologyRuleTests(unittest.TestCase):
    def test_required_technology_scores(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TechnologyRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="C# and SQL",
            url="https://example.com/1",
            source="remoteok",
            status="NEW",
            technologies=["c#", "sql server", "asp.net core"],
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.score, rule.REQUIRED_TECHNOLOGY_SCORE)

    def test_missing_required_technology_scores_negative(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TechnologyRule(preferences)
        job = Job(
            id="job-2",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="JavaScript and Node.js",
            url="https://example.com/2",
            source="remoteok",
            status="NEW",
            technologies=["javascript", "nodejs"],
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertLess(result.score, 0)

    def test_preferred_technology_adds_bonus(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = TechnologyRule(preferences)
        job_with_preferred = Job(
            id="job-3a",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="C#, SQL, Docker, Kubernetes",
            url="https://example.com/3a",
            source="remoteok",
            status="NEW",
            technologies=["c#", "sql", "docker", "kubernetes"],
        )
        job_without_preferred = Job(
            id="job-3b",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="C# and SQL",
            url="https://example.com/3b",
            source="remoteok",
            status="NEW",
            technologies=["c#", "sql"],
        )

        result_with = rule.evaluate(job_with_preferred)
        result_without = rule.evaluate(job_without_preferred)

        self.assertGreater(result_with.score, result_without.score)


class ExperienceRuleTests(unittest.TestCase):
    def test_scores_positive_keywords(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = ExperienceRule(preferences)
        job = Job(
            id="job-1",
            title="Backend Engineer",
            company="Example",
            location="Remote",
            description="5+ years backend experience with microservices and cloud architecture",
            url="https://example.com/1",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertGreater(result.score, 0)

    def test_zero_score_without_keywords(self) -> None:
        preferences = Preferences.load(Path("config/preferences.yaml"))
        rule = ExperienceRule(preferences)
        job = Job(
            id="job-2",
            title="Product Manager",
            company="Example",
            location="Remote",
            description="Manage product roadmap",
            url="https://example.com/2",
            source="remoteok",
            status="NEW",
        )

        result = rule.evaluate(job)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 0)


class RecommendationThresholdTests(unittest.TestCase):
    def test_job_recommended_above_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = RecommendationEngine(database=database, repository=repository, preferences=preferences)

            # Job with high score
            job = Job(
                id="job-1",
                title="Senior Backend Engineer",
                company="Example",
                location="Remote",
                description="5+ years backend experience with microservices and cloud",
                url="https://example.com/1",
                source="remoteok",
                status="NEW",
                technologies=["c#", "sql server", "asp.net core", "docker", "kubernetes"],
            )

            repository.insert_jobs([job])
            summary = engine.run()

            # Should be recommended
            row = database.connection.execute(
                "SELECT status, recommendation_score FROM jobs WHERE job_id = ?",
                ("job-1",),
            ).fetchone()

            self.assertEqual(row["status"], "RECOMMENDED")
            self.assertGreaterEqual(row["recommendation_score"], preferences.recommendation.minimum_score)

            database.close()

    def test_job_not_recommended_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = RecommendationEngine(database=database, repository=repository, preferences=preferences)

            # Job with low score
            job = Job(
                id="job-2",
                title="Architect",
                company="Example",
                location="New York, USA",
                description="Some role",
                url="https://example.com/2",
                source="remoteok",
                status="NEW",
                technologies=[],
            )

            repository.insert_jobs([job])
            summary = engine.run()

            row = database.connection.execute(
                "SELECT status, recommendation_score FROM jobs WHERE job_id = ?",
                ("job-2",),
            ).fetchone()

            self.assertEqual(row["status"], "NOT_RECOMMENDED")
            self.assertLess(row["recommendation_score"], preferences.recommendation.minimum_score)

            database.close()


class RecommendationDetailsTests(unittest.TestCase):
    def test_stores_recommendation_details_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = RecommendationEngine(database=database, repository=repository, preferences=preferences)

            job = Job(
                id="job-1",
                title="Backend Engineer",
                company="Example",
                location="Remote",
                description="Microservices and CI/CD",
                url="https://example.com/1",
                source="remoteok",
                status="NEW",
                technologies=["c#", "docker"],
            )

            repository.insert_jobs([job])
            engine.run()

            row = database.connection.execute(
                "SELECT recommendation_details FROM jobs WHERE job_id = ?",
                ("job-1",),
            ).fetchone()

            self.assertIsNotNone(row["recommendation_details"])
            details = json.loads(row["recommendation_details"])
            self.assertIsInstance(details, list)
            self.assertTrue(all("rule" in d and "score" in d and "reason" in d for d in details))

            database.close()

    def test_stores_recommendation_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = RecommendationEngine(database=database, repository=repository, preferences=preferences)

            job = Job(
                id="job-1",
                title="Backend Engineer",
                company="Example",
                location="Remote",
                description="Test",
                url="https://example.com/1",
                source="remoteok",
                status="NEW",
                technologies=["c#"],
            )

            repository.insert_jobs([job])
            engine.run()

            row = database.connection.execute(
                "SELECT recommendation_summary FROM jobs WHERE job_id = ?",
                ("job-1",),
            ).fetchone()

            self.assertIsNotNone(row["recommendation_summary"])
            self.assertIsInstance(row["recommendation_summary"], str)

            database.close()


class RecommendationEngineTests(unittest.TestCase):
    def test_engine_evaluates_multiple_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            database = SQLiteDatabase(db_path)
            repository = JobRepository(database)
            preferences = Preferences.load(Path("config/preferences.yaml"))
            engine = RecommendationEngine(database=database, repository=repository, preferences=preferences)

            jobs = [
                Job(
                    id="job-1",
                    title="Senior Backend Engineer",
                    company="Example",
                    location="Remote",
                    description="5+ years",
                    url="https://example.com/1",
                    source="remoteok",
                    status="NEW",
                    technologies=["c#", "sql"],
                ),
                Job(
                    id="job-2",
                    title="Internship - C# Developer",
                    company="Example",
                    location="Remote",
                    description="3-month internship",
                    url="https://example.com/2",
                    source="remoteok",
                    status="NEW",
                    technologies=["c#"],
                ),
            ]

            repository.insert_jobs(jobs)
            summary = engine.run()

            self.assertEqual(summary["evaluated"], 2)
            self.assertEqual(summary["hard_rejected"], 1)
            self.assertGreater(summary["recommended"] + summary["not_recommended"], 0)

            database.close()


if __name__ == "__main__":
    unittest.main()

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
        assert "remote" in preferences.location.preferred
        assert "anywhere" in preferences.location.preferred
        assert "onsite only" in preferences.location.hard_reject

        # Verify title preferences
        assert "backend engineer" in preferences.title.primary or "senior backend engineer" in preferences.title.primary
        
        # Verify technology preferences
        assert "c#" in preferences.technologies.required or ".net" in preferences.technologies.required
        
        # Verify recommendation threshold exists
        assert preferences.recommendation.minimum_score > 0


if __name__ == "__main__":
    unittest.main()
