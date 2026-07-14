"""Tests for Milestone 6 - AI Provider Foundation and Profile Refactor."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from config.profile import Profile, SkillsProfile, ExperienceProfile, AvailabilityProfile
from core.analysis.analysis_result import AnalysisResult
from core.analysis.mock_provider import MockProvider
from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_analysis_repository import JobAnalysisRepository
from infrastructure.sqlite.job_repository import JobRepository
from workflows.job_analysis_workflow import JobAnalysisWorkflow


class SkillsProfileDynamicTests(unittest.TestCase):
    """Test dynamic skills profile functionality."""

    def test_skills_stores_dynamic_categories(self) -> None:
        """Skills should store dynamic categories."""
        skills = SkillsProfile(
            categories={
                "core": ["C#", ".NET"],
                "cloud": ["Azure", "AWS"],
                "devops": ["Docker", "Kubernetes"],
            }
        )

        self.assertEqual(len(skills.categories), 3)
        self.assertIn("core", skills.categories)

    def test_skills_get_category(self) -> None:
        """Should retrieve skills by category."""
        skills = SkillsProfile(categories={"core": ["C#", ".NET"]})

        core_skills = skills.get("core")
        self.assertEqual(len(core_skills), 2)
        self.assertIn("C#", core_skills)

    def test_skills_get_case_insensitive(self) -> None:
        """Get should work case-insensitively."""
        skills = SkillsProfile(categories={"CORE": ["C#"]})

        self.assertEqual(len(skills.get("core")), 1)
        self.assertEqual(len(skills.get("Core")), 1)
        self.assertEqual(len(skills.get("CORE")), 1)

    def test_skills_all_skills_deduplicated(self) -> None:
        """All skills should be deduplicated."""
        skills = SkillsProfile(
            categories={
                "core": ["C#", "c#", "C#"],
                "primary": ["Python", "python"],
            }
        )

        all_skills = skills.all_skills()
        
        # Should have only unique skills
        self.assertLess(len(all_skills), 5)
        self.assertIn("c#", all_skills)
        self.assertIn("python", all_skills)

    def test_skills_all_skills_lowercase(self) -> None:
        """All skills should be lowercase."""
        skills = SkillsProfile(categories={"core": ["C#", "PYTHON", ".NET"]})

        all_skills = skills.all_skills()
        
        for skill in all_skills:
            self.assertEqual(skill, skill.lower())

    def test_skills_all_skills_sorted(self) -> None:
        """All skills should be sorted deterministically."""
        skills = SkillsProfile(categories={"core": ["Zebra", "Apple", "Banana"]})

        all_skills = skills.all_skills()
        
        # Should be sorted
        self.assertEqual(all_skills, sorted(all_skills))

    def test_skills_all_skills_trimmed(self) -> None:
        """All skills should have whitespace trimmed."""
        skills = SkillsProfile(categories={"core": [" C# ", "  Python  ", "\t.NET\n"]})

        all_skills = skills.all_skills()
        
        for skill in all_skills:
            self.assertEqual(skill, skill.strip())

    def test_skills_category_names(self) -> None:
        """Should list category names."""
        skills = SkillsProfile(
            categories={"core": ["C#"], "cloud": ["Azure"]}
        )

        names = skills.category_names()
        
        self.assertEqual(len(names), 2)
        self.assertIn("core", names)
        self.assertIn("cloud", names)

    def test_skills_category_names_sorted(self) -> None:
        """Category names should be sorted."""
        skills = SkillsProfile(
            categories={"zebra": ["Z"], "apple": ["A"], "banana": ["B"]}
        )

        names = skills.category_names()
        
        self.assertEqual(names, sorted(names))

    def test_skills_primary_skills(self) -> None:
        """Should get primary skills from core category."""
        skills = SkillsProfile(
            categories={
                "core": ["C#", ".NET"],
                "secondary": ["Python"],
            }
        )

        primary = skills.primary_skills()
        
        self.assertEqual(primary, ["C#", ".NET"])

    def test_skills_has_skill(self) -> None:
        """Should check if skill exists."""
        skills = SkillsProfile(categories={"core": ["C#", ".NET", "Python"]})

        self.assertTrue(skills.has_skill("C#"))
        self.assertTrue(skills.has_skill("python"))
        self.assertFalse(skills.has_skill("Ruby"))

    def test_skills_has_category(self) -> None:
        """Should check if category exists."""
        skills = SkillsProfile(categories={"core": ["C#"], "cloud": ["Azure"]})

        self.assertTrue(skills.has_category("core"))
        self.assertTrue(skills.has_category("CORE"))
        self.assertFalse(skills.has_category("devops"))


class ProfileValidationTests(unittest.TestCase):
    """Test profile validation."""

    def test_profile_validation_requires_name(self) -> None:
        """Profile should require name."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("title: Engineer\nexperience: {years: 5}\nskills: {core: [C#]}")
            f.flush()
            
            with self.assertRaises(ValueError) as cm:
                Profile.load(f.name)
            
            self.assertIn("name", str(cm.exception).lower())

    def test_profile_validation_requires_experience_years(self) -> None:
        """Profile should require experience.years."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("name: Test\ntitle: Engineer\nexperience: {}\nskills: {core: [C#]}")
            f.flush()
            
            with self.assertRaises(ValueError) as cm:
                Profile.load(f.name)
            
            # Should mention experience, not just years
            self.assertIn("experience", str(cm.exception).lower())

    def test_profile_validation_requires_skills(self) -> None:
        """Profile should require skills section."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("name: Test\ntitle: Engineer\nexperience: {years: 5}")
            f.flush()
            
            with self.assertRaises(ValueError) as cm:
                Profile.load(f.name)
            
            self.assertIn("skills", str(cm.exception))


class ProfileLoadingTests(unittest.TestCase):
    """Test profile loading and features."""

    def test_profile_loads_from_config(self) -> None:
        """Profile should load from config/profile.yaml."""
        profile = Profile.load()

        self.assertIsNotNone(profile.name)
        self.assertIsNotNone(profile.title)
        self.assertGreater(profile.experience.years, 0)
        self.assertGreater(len(profile.skills.categories), 0)

    def test_profile_loads_dynamic_skill_categories(self) -> None:
        """Profile should load dynamic skill categories."""
        profile = Profile.load()

        categories = profile.skills.category_names()
        self.assertGreater(len(categories), 0)
        # Should have various categories
        self.assertTrue(any(cat for cat in categories))

    def test_profile_skill_deduplication(self) -> None:
        """Profile skills should be deduplicated and normalized."""
        profile = Profile.load()
        all_skills = profile.skills.all_skills()

        self.assertGreater(len(all_skills), 0)
        # All skills should be lowercase
        for skill in all_skills:
            self.assertEqual(skill, skill.lower())
        
        # All skills should be unique
        self.assertEqual(len(all_skills), len(set(all_skills)))

    def test_profile_loads_additional_sections(self) -> None:
        """Profile should load additional sections."""
        profile = Profile.load()

        # These sections should be loaded from expanded profile.yaml
        self.assertIsNotNone(profile.strengths)
        self.assertIsNotNone(profile.preferred_domains)
        self.assertIsNotNone(profile.preferred_roles)

    def test_profile_loads_resume_profiles(self) -> None:
        """Profile should load resume_profiles section."""
        profile = Profile.load()

        self.assertIsInstance(profile.resume_profiles, dict)

    def test_profile_loads_career_goals(self) -> None:
        """Profile should load career_goals section."""
        profile = Profile.load()

        self.assertIsInstance(profile.career_goals, dict)

    def test_profile_custom_path(self) -> None:
        """Profile should load from custom path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
name: Custom Profile
title: Engineer
location: Remote
experience:
  years: 5
  summary: Test
skills:
  core:
    - C#
    - Python
""")
            f.flush()
            
            profile = Profile.load(f.name)
            self.assertEqual(profile.name, "Custom Profile")


class ProfileHelperMethodsTests(unittest.TestCase):
    """Test profile helper methods."""

    def test_profile_primary_skills(self) -> None:
        """Profile should return primary skills."""
        profile = Profile.load()
        primary = profile.primary_skills()

        self.assertGreater(len(primary), 0)

    def test_profile_has_skill(self) -> None:
        """Profile should check for skills."""
        profile = Profile.load()

        # Should have C# based on expanded profile
        self.assertTrue(profile.has_skill("c#") or profile.has_skill("python"))

    def test_profile_has_category(self) -> None:
        """Profile should check for categories."""
        profile = Profile.load()

        categories = profile.skills.category_names()
        if categories:
            first_category = categories[0]
            self.assertTrue(profile.has_category(first_category))

    def test_profile_resume(self) -> None:
        """Profile should retrieve resume by name."""
        profile = Profile.load()

        # resume() should exist and work
        result = profile.resume("backend")
        # Result could be None or a filename
        self.assertTrue(result is None or isinstance(result, str))

    def test_profile_summary_for_ai(self) -> None:
        """Profile should generate AI summary."""
        profile = Profile.load()

        summary = profile.summary_for_ai()
        
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 0)
        self.assertIn(profile.name, summary)
        self.assertIn(profile.title, summary)


class ProfileBackwardCompatibilityTests(unittest.TestCase):
    """Test backward compatibility of profile module."""

    def test_profile_load_without_args(self) -> None:
        """Profile.load() without arguments should work."""
        # This should use default path
        profile = Profile.load()
        self.assertIsNotNone(profile.name)

    def test_profile_skills_all_skills(self) -> None:
        """profile.skills.all_skills() should continue working."""
        profile = Profile.load()

        all_skills = profile.skills.all_skills()
        
        self.assertIsInstance(all_skills, list)
        self.assertGreater(len(all_skills), 0)


class AnalysisResultTests(unittest.TestCase):
    """Test analysis result data structure."""

    def test_analysis_result_has_all_fields(self) -> None:
        """Analysis result should store all required fields."""
        result = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great fit",
            strengths=["Skill1", "Skill2"],
            missing_skills=["Skill3"],
            recommended_resume="Resume text",
            email_highlights="Email text",
            confidence=85,
        )

        self.assertEqual(result.job_id, "job123")
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.match_summary, "Great fit")
        self.assertEqual(len(result.strengths), 2)
        self.assertEqual(len(result.missing_skills), 1)
        self.assertEqual(result.confidence, 85)

    def test_analysis_result_to_dict(self) -> None:
        """Analysis result should convert to dictionary."""
        result = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great fit",
            strengths=["S1", "S2"],
            missing_skills=["M1"],
            recommended_resume="Resume",
            email_highlights="Email",
            confidence=90,
        )

        d = result.to_dict()
        self.assertEqual(d["job_id"], "job123")
        self.assertEqual(d["provider"], "mock")
        self.assertEqual(d["confidence"], 90)
        self.assertEqual(len(d["strengths"]), 2)


class MockProviderTests(unittest.TestCase):
    """Test MockProvider analysis generation."""

    def test_mock_provider_has_name(self) -> None:
        """Mock provider should have identifier."""
        profile = Profile.load()
        provider = MockProvider(profile)

        self.assertEqual(provider.name, "mock")

    def test_mock_provider_analyzes_job(self) -> None:
        """Mock provider should generate analysis for job."""
        profile = Profile.load()
        provider = MockProvider(profile)

        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET experience required",
        )

        result = provider.analyze(job)

        self.assertEqual(result.job_id, "job123")
        self.assertEqual(result.provider, "mock")
        self.assertGreater(len(result.match_summary), 0)
        self.assertGreater(len(result.strengths), 0)
        self.assertGreaterEqual(result.confidence, 70)
        self.assertLessEqual(result.confidence, 100)

    def test_mock_provider_generates_deterministic_results(self) -> None:
        """Mock provider should generate same analysis for same job."""
        profile = Profile.load()
        provider = MockProvider(profile)

        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET",
        )

        result1 = provider.analyze(job)
        result2 = provider.analyze(job)

        self.assertEqual(result1.confidence, result2.confidence)
        self.assertEqual(result1.match_summary, result2.match_summary)

    def test_mock_provider_uses_primary_skills(self) -> None:
        """Mock provider should use profile primary skills."""
        profile = Profile.load()
        provider = MockProvider(profile)

        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="Backend development",
        )

        result = provider.analyze(job)

        self.assertGreater(len(result.email_highlights), 0)
        # Should mention experience years
        self.assertIn(str(profile.experience.years), result.email_highlights)


class JobAnalysisRepositoryTests(unittest.TestCase):
    """Test job analysis repository."""

    def setUp(self) -> None:
        """Set up test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.database = SQLiteDatabase(self.db_path)
        self.repository = JobAnalysisRepository(self.database)

    def tearDown(self) -> None:
        """Clean up test database."""
        self.database.close()
        self.temp_dir.cleanup()

    def test_repository_saves_analysis(self) -> None:
        """Repository should save analysis to database."""
        analysis = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great fit",
            strengths=["S1", "S2"],
            missing_skills=["M1"],
            recommended_resume="Resume",
            email_highlights="Email",
            confidence=85,
        )

        self.repository.save(analysis)

        # Verify saved
        saved = self.repository.get_by_job_and_provider("job123", "mock")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.confidence, 85)

    def test_repository_prevents_duplicate_analysis(self) -> None:
        """Repository should prevent duplicate analysis for same job/provider."""
        analysis1 = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Fit 1",
            strengths=["S1"],
            missing_skills=["M1"],
            recommended_resume="Resume1",
            email_highlights="Email1",
            confidence=80,
        )

        analysis2 = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Fit 2",
            strengths=["S2"],
            missing_skills=["M2"],
            recommended_resume="Resume2",
            email_highlights="Email2",
            confidence=90,
        )

        self.repository.save(analysis1)
        self.repository.save(analysis2)

        # Last one should win
        saved = self.repository.get_by_job_and_provider("job123", "mock")
        self.assertEqual(saved.confidence, 90)

    def test_repository_retrieves_analysis(self) -> None:
        """Repository should retrieve saved analysis."""
        analysis = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great",
            strengths=["Backend", "Cloud"],
            missing_skills=["Kubernetes"],
            recommended_resume="Resume text",
            email_highlights="Email text",
            confidence=88,
        )

        self.repository.save(analysis)
        retrieved = self.repository.get_by_job_and_provider("job123", "mock")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_id, "job123")
        self.assertEqual(retrieved.strengths, ["Backend", "Cloud"])
        self.assertEqual(retrieved.confidence, 88)

    def test_repository_check_has_analysis(self) -> None:
        """Repository should check if analysis exists."""
        analysis = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great",
            strengths=["S1"],
            missing_skills=["M1"],
            recommended_resume="Resume",
            email_highlights="Email",
            confidence=85,
        )

        self.assertFalse(self.repository.has_analysis("job123", "mock"))
        self.repository.save(analysis)
        self.assertTrue(self.repository.has_analysis("job123", "mock"))

    def test_repository_counts_by_provider(self) -> None:
        """Repository should count analyses by provider."""
        for i in range(3):
            analysis = AnalysisResult(
                job_id=f"job{i}",
                provider="mock",
                match_summary="Great",
                strengths=["S1"],
                missing_skills=["M1"],
                recommended_resume="Resume",
                email_highlights="Email",
                confidence=85,
            )
            self.repository.save(analysis)

        count = self.repository.count_by_provider("mock")
        self.assertEqual(count, 3)


class JobAnalysisWorkflowTests(unittest.TestCase):
    """Test job analysis workflow."""

    def setUp(self) -> None:
        """Set up test database and workflow."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.database = SQLiteDatabase(self.db_path)
        self.job_repository = JobRepository(self.database)
        self.profile = Profile.load()
        self.workflow = JobAnalysisWorkflow(
            database=self.database,
            job_repository=self.job_repository,
            profile=self.profile,
        )

    def tearDown(self) -> None:
        """Clean up test database."""
        self.database.close()
        self.temp_dir.cleanup()

    def test_workflow_analyzes_recommended_jobs(self) -> None:
        """Workflow should analyze recommended jobs."""
        # Insert a recommended job
        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET required",
            status="RECOMMENDED",
        )
        self.job_repository.insert_jobs([job])

        result = self.workflow.run()

        self.assertEqual(result["recommended_jobs"], 1)
        self.assertEqual(result["new_analyses"], 1)
        self.assertEqual(result["already_analyzed"], 0)

    def test_workflow_skips_already_analyzed_jobs(self) -> None:
        """Workflow should skip jobs already analyzed by provider."""
        # Insert a recommended job
        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET",
            status="RECOMMENDED",
        )
        self.job_repository.insert_jobs([job])

        # First run
        result1 = self.workflow.run()
        self.assertEqual(result1["new_analyses"], 1)

        # Second run - should skip
        result2 = self.workflow.run()
        self.assertEqual(result2["new_analyses"], 0)
        self.assertEqual(result2["already_analyzed"], 1)

    def test_workflow_ignores_non_recommended_jobs(self) -> None:
        """Workflow should only analyze RECOMMENDED jobs."""
        # Insert jobs with different statuses
        jobs = [
            Job(
                id="job1",
                title="Backend Engineer",
                company="Corp1",
                location="Remote",
                url="https://example.com/1",
                source="test",
                description="C# and .NET",
                status="NEW",
            ),
            Job(
                id="job2",
                title="Backend Developer",
                company="Corp2",
                location="Remote",
                url="https://example.com/2",
                source="test",
                description="C# and .NET",
                status="NOT_RECOMMENDED",
            ),
            Job(
                id="job3",
                title="Senior Backend",
                company="Corp3",
                location="Remote",
                url="https://example.com/3",
                source="test",
                description="C# and .NET",
                status="HARD_REJECTED",
            ),
        ]
        self.job_repository.insert_jobs(jobs)

        result = self.workflow.run()

        # No RECOMMENDED jobs, so no analyses
        self.assertEqual(result["recommended_jobs"], 0)
        self.assertEqual(result["new_analyses"], 0)

    def test_workflow_returns_execution_statistics(self) -> None:
        """Workflow should return execution statistics."""
        result = self.workflow.run()

        self.assertIn("recommended_jobs", result)
        self.assertIn("already_analyzed", result)
        self.assertIn("new_analyses", result)
        self.assertIn("execution_time", result)
        self.assertGreaterEqual(result["execution_time"], 0)


if __name__ == "__main__":
    unittest.main()





class AnalysisResultTests(unittest.TestCase):
    """Test analysis result data structure."""

    def test_analysis_result_has_all_fields(self) -> None:
        """Analysis result should store all required fields."""
        result = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great fit",
            strengths=["Skill1", "Skill2"],
            missing_skills=["Skill3"],
            recommended_resume="Resume text",
            email_highlights="Email text",
            confidence=85,
        )

        self.assertEqual(result.job_id, "job123")
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.match_summary, "Great fit")
        self.assertEqual(len(result.strengths), 2)
        self.assertEqual(len(result.missing_skills), 1)
        self.assertEqual(result.confidence, 85)

    def test_analysis_result_to_dict(self) -> None:
        """Analysis result should convert to dictionary."""
        result = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great fit",
            strengths=["S1", "S2"],
            missing_skills=["M1"],
            recommended_resume="Resume",
            email_highlights="Email",
            confidence=90,
        )

        d = result.to_dict()
        self.assertEqual(d["job_id"], "job123")
        self.assertEqual(d["provider"], "mock")
        self.assertEqual(d["confidence"], 90)
        self.assertEqual(len(d["strengths"]), 2)


class MockProviderTests(unittest.TestCase):
    """Test MockProvider analysis generation."""

    def test_mock_provider_has_name(self) -> None:
        """Mock provider should have identifier."""
        profile = Profile.load()
        provider = MockProvider(profile)

        self.assertEqual(provider.name, "mock")

    def test_mock_provider_analyzes_job(self) -> None:
        """Mock provider should generate analysis for job."""
        profile = Profile.load()
        provider = MockProvider(profile)

        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET experience required",
        )

        result = provider.analyze(job)

        self.assertEqual(result.job_id, "job123")
        self.assertEqual(result.provider, "mock")
        self.assertGreater(len(result.match_summary), 0)
        self.assertGreater(len(result.strengths), 0)
        self.assertGreaterEqual(result.confidence, 70)
        self.assertLessEqual(result.confidence, 100)

    def test_mock_provider_generates_deterministic_results(self) -> None:
        """Mock provider should generate same analysis for same job."""
        profile = Profile.load()
        provider = MockProvider(profile)

        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET",
        )

        result1 = provider.analyze(job)
        result2 = provider.analyze(job)

        self.assertEqual(result1.confidence, result2.confidence)
        self.assertEqual(result1.match_summary, result2.match_summary)

    def test_mock_provider_uses_primary_skills(self) -> None:
        """Mock provider should use profile primary skills."""
        profile = Profile.load()
        provider = MockProvider(profile)

        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="Backend development",
        )

        result = provider.analyze(job)

        self.assertGreater(len(result.email_highlights), 0)
        # Should mention experience years
        self.assertIn(str(profile.experience.years), result.email_highlights)


class JobAnalysisRepositoryTests(unittest.TestCase):
    """Test job analysis repository."""

    def setUp(self) -> None:
        """Set up test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.database = SQLiteDatabase(self.db_path)
        self.repository = JobAnalysisRepository(self.database)

    def tearDown(self) -> None:
        """Clean up test database."""
        self.database.close()
        self.temp_dir.cleanup()

    def test_repository_saves_analysis(self) -> None:
        """Repository should save analysis to database."""
        analysis = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great fit",
            strengths=["S1", "S2"],
            missing_skills=["M1"],
            recommended_resume="Resume",
            email_highlights="Email",
            confidence=85,
        )

        self.repository.save(analysis)

        # Verify saved
        saved = self.repository.get_by_job_and_provider("job123", "mock")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.confidence, 85)

    def test_repository_prevents_duplicate_analysis(self) -> None:
        """Repository should prevent duplicate analysis for same job/provider."""
        analysis1 = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Fit 1",
            strengths=["S1"],
            missing_skills=["M1"],
            recommended_resume="Resume1",
            email_highlights="Email1",
            confidence=80,
        )

        analysis2 = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Fit 2",
            strengths=["S2"],
            missing_skills=["M2"],
            recommended_resume="Resume2",
            email_highlights="Email2",
            confidence=90,
        )

        self.repository.save(analysis1)
        self.repository.save(analysis2)

        # Last one should win
        saved = self.repository.get_by_job_and_provider("job123", "mock")
        self.assertEqual(saved.confidence, 90)

    def test_repository_retrieves_analysis(self) -> None:
        """Repository should retrieve saved analysis."""
        analysis = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great",
            strengths=["Backend", "Cloud"],
            missing_skills=["Kubernetes"],
            recommended_resume="Resume text",
            email_highlights="Email text",
            confidence=88,
        )

        self.repository.save(analysis)
        retrieved = self.repository.get_by_job_and_provider("job123", "mock")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_id, "job123")
        self.assertEqual(retrieved.strengths, ["Backend", "Cloud"])
        self.assertEqual(retrieved.confidence, 88)

    def test_repository_check_has_analysis(self) -> None:
        """Repository should check if analysis exists."""
        analysis = AnalysisResult(
            job_id="job123",
            provider="mock",
            match_summary="Great",
            strengths=["S1"],
            missing_skills=["M1"],
            recommended_resume="Resume",
            email_highlights="Email",
            confidence=85,
        )

        self.assertFalse(self.repository.has_analysis("job123", "mock"))
        self.repository.save(analysis)
        self.assertTrue(self.repository.has_analysis("job123", "mock"))

    def test_repository_counts_by_provider(self) -> None:
        """Repository should count analyses by provider."""
        for i in range(3):
            analysis = AnalysisResult(
                job_id=f"job{i}",
                provider="mock",
                match_summary="Great",
                strengths=["S1"],
                missing_skills=["M1"],
                recommended_resume="Resume",
                email_highlights="Email",
                confidence=85,
            )
            self.repository.save(analysis)

        count = self.repository.count_by_provider("mock")
        self.assertEqual(count, 3)


class JobAnalysisWorkflowTests(unittest.TestCase):
    """Test job analysis workflow."""

    def setUp(self) -> None:
        """Set up test database and workflow."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.database = SQLiteDatabase(self.db_path)
        self.job_repository = JobRepository(self.database)
        self.profile = Profile.load()
        self.workflow = JobAnalysisWorkflow(
            database=self.database,
            job_repository=self.job_repository,
            profile=self.profile,
        )

    def tearDown(self) -> None:
        """Clean up test database."""
        self.database.close()
        self.temp_dir.cleanup()

    def test_workflow_analyzes_recommended_jobs(self) -> None:
        """Workflow should analyze recommended jobs."""
        # Insert a recommended job
        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET required",
            status="RECOMMENDED",
        )
        self.job_repository.insert_jobs([job])

        result = self.workflow.run()

        self.assertEqual(result["recommended_jobs"], 1)
        self.assertEqual(result["new_analyses"], 1)
        self.assertEqual(result["already_analyzed"], 0)

    def test_workflow_skips_already_analyzed_jobs(self) -> None:
        """Workflow should skip jobs already analyzed by provider."""
        # Insert a recommended job
        job = Job(
            id="job123",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com",
            source="test",
            description="C# and .NET",
            status="RECOMMENDED",
        )
        self.job_repository.insert_jobs([job])

        # First run
        result1 = self.workflow.run()
        self.assertEqual(result1["new_analyses"], 1)

        # Second run - should skip
        result2 = self.workflow.run()
        self.assertEqual(result2["new_analyses"], 0)
        self.assertEqual(result2["already_analyzed"], 1)

    def test_workflow_ignores_non_recommended_jobs(self) -> None:
        """Workflow should only analyze RECOMMENDED jobs."""
        # Insert jobs with different statuses
        jobs = [
            Job(
                id="job1",
                title="Backend Engineer",
                company="Corp1",
                location="Remote",
                url="https://example.com/1",
                source="test",
                description="C# and .NET",
                status="NEW",
            ),
            Job(
                id="job2",
                title="Backend Developer",
                company="Corp2",
                location="Remote",
                url="https://example.com/2",
                source="test",
                description="C# and .NET",
                status="NOT_RECOMMENDED",
            ),
            Job(
                id="job3",
                title="Senior Backend",
                company="Corp3",
                location="Remote",
                url="https://example.com/3",
                source="test",
                description="C# and .NET",
                status="HARD_REJECTED",
            ),
        ]
        self.job_repository.insert_jobs(jobs)

        result = self.workflow.run()

        # No RECOMMENDED jobs, so no analyses
        self.assertEqual(result["recommended_jobs"], 0)
        self.assertEqual(result["new_analyses"], 0)

    def test_workflow_returns_execution_statistics(self) -> None:
        """Workflow should return execution statistics."""
        result = self.workflow.run()

        self.assertIn("recommended_jobs", result)
        self.assertIn("already_analyzed", result)
        self.assertIn("new_analyses", result)
        self.assertIn("execution_time", result)
        self.assertGreaterEqual(result["execution_time"], 0)


if __name__ == "__main__":
    unittest.main()
