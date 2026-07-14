"""Tests for Milestone 7 - Recruiter Discovery."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from domain.job import Job
from app.recruiter.base import DiscoveryStrategy
from app.recruiter.models import RecruiterContact
from app.recruiter.service import RecruiterDiscoveryService
from app.recruiter.strategies import (
    CommonAddressStrategy,
    CompanyCareersPageStrategy,
    CompanyContactPageStrategy,
    GreenhouseStrategy,
)
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository
from workflows.recruiter_discovery_workflow import RecruiterDiscoveryWorkflow


class RecruiterContactTests(unittest.TestCase):
    """Test RecruiterContact model."""

    def test_recruiter_contact_creation(self) -> None:
        """RecruiterContact should store all fields."""
        contact = RecruiterContact(
            email="recruiter@company.com",
            name="John Recruiter",
            source="greenhouse",
            confidence=85,
        )

        self.assertEqual(contact.email, "recruiter@company.com")
        self.assertEqual(contact.name, "John Recruiter")
        self.assertEqual(contact.source, "greenhouse")
        self.assertEqual(contact.confidence, 85)

    def test_recruiter_contact_frozen(self) -> None:
        """RecruiterContact should be immutable."""
        contact = RecruiterContact(
            email="recruiter@company.com",
            name="John",
            source="greenhouse",
            confidence=85,
        )

        with self.assertRaises(AttributeError):
            contact.email = "new@email.com"

    def test_recruiter_contact_invalid_email(self) -> None:
        """RecruiterContact should validate email."""
        with self.assertRaises(ValueError):
            RecruiterContact(
                email="invalid",
                name="John",
                source="greenhouse",
                confidence=85,
            )

    def test_recruiter_contact_invalid_confidence(self) -> None:
        """RecruiterContact should validate confidence range."""
        with self.assertRaises(ValueError):
            RecruiterContact(
                email="recruiter@company.com",
                name="John",
                source="greenhouse",
                confidence=150,
            )


class GreenhouseStrategyTests(unittest.TestCase):
    """Test Greenhouse recruiter discovery strategy."""

    def setUp(self) -> None:
        self.strategy = GreenhouseStrategy()

    def test_greenhouse_strategy_name(self) -> None:
        """Strategy should have correct name."""
        self.assertEqual(self.strategy.name, "greenhouse")

    def test_greenhouse_strategy_identifies_greenhouse_job(self) -> None:
        """Strategy should identify Greenhouse job board."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.greenhouse.io/jobs/123",
            source="greenhouse",
            description="Contact us at jobs@techcorp.com",
        )

        contact = self.strategy.discover(job)

        self.assertIsNotNone(contact)
        self.assertEqual(contact.email, "jobs@techcorp.com")
        self.assertEqual(contact.source, "greenhouse_metadata")

    def test_greenhouse_strategy_ignores_non_greenhouse_jobs(self) -> None:
        """Strategy should ignore non-Greenhouse jobs."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com/careers/123",
            source="other",
            description="Some job description",
        )

        contact = self.strategy.discover(job)

        self.assertIsNone(contact)

    def test_greenhouse_strategy_extracts_email_patterns(self) -> None:
        """Strategy should extract email from common patterns."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.greenhouse.io/jobs/123",
            source="greenhouse",
            description="Questions? Contact: contact@techcorp.com",
        )

        contact = self.strategy.discover(job)

        self.assertIsNotNone(contact)
        self.assertEqual(contact.email, "contact@techcorp.com")


class CompanyCareersPageStrategyTests(unittest.TestCase):
    """Test Company Careers Page strategy."""

    def setUp(self) -> None:
        self.strategy = CompanyCareersPageStrategy()

    def test_company_careers_page_strategy_name(self) -> None:
        """Strategy should have correct name."""
        self.assertEqual(self.strategy.name, "company_careers_page")

    def test_company_careers_page_strategy_extracts_email(self) -> None:
        """Strategy should extract careers email."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com/careers/123",
            source="website",
            description="For careers inquiries: careers@techcorp.com",
        )

        contact = self.strategy.discover(job)

        self.assertIsNotNone(contact)
        self.assertEqual(contact.email, "careers@techcorp.com")

    def test_company_careers_page_strategy_requires_url(self) -> None:
        """Strategy should require URL."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="",
            source="website",
            description="careers@techcorp.com",
        )

        contact = self.strategy.discover(job)

        self.assertIsNone(contact)


class CompanyContactPageStrategyTests(unittest.TestCase):
    """Test Company Contact Page strategy."""

    def setUp(self) -> None:
        self.strategy = CompanyContactPageStrategy()

    def test_company_contact_page_strategy_name(self) -> None:
        """Strategy should have correct name."""
        self.assertEqual(self.strategy.name, "company_contact_page")

    def test_company_contact_page_strategy_extracts_hiring_email(self) -> None:
        """Strategy should extract hiring email."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com/contact",
            source="website",
            description="For hiring inquiries: hiring@techcorp.com",
        )

        contact = self.strategy.discover(job)

        self.assertIsNotNone(contact)
        self.assertEqual(contact.email, "hiring@techcorp.com")

    def test_company_contact_page_strategy_requires_description(self) -> None:
        """Strategy should require description."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com",
            source="website",
            description="",
        )

        contact = self.strategy.discover(job)

        self.assertIsNone(contact)


class CommonAddressStrategyTests(unittest.TestCase):
    """Test Common Address strategy."""

    def setUp(self) -> None:
        self.strategy = CommonAddressStrategy()

    def test_common_address_strategy_name(self) -> None:
        """Strategy should have correct name."""
        self.assertEqual(self.strategy.name, "common_address")

    def test_common_address_strategy_generates_email(self) -> None:
        """Strategy should generate common addressing."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com/careers/123",
            source="website",
            description="",
        )

        contact = self.strategy.discover(job)

        self.assertIsNotNone(contact)
        self.assertIn("@techcorp.com", contact.email)
        self.assertEqual(contact.source, "common_address")
        self.assertEqual(contact.confidence, 40)  # Lower confidence for generated

    def test_common_address_strategy_extracts_domain(self) -> None:
        """Strategy should extract domain correctly."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://subdomain.techcorp.com/careers/123",
            source="website",
            description="",
        )

        contact = self.strategy.discover(job)

        self.assertIsNotNone(contact)
        self.assertIn("techcorp.com", contact.email)

    def test_common_address_strategy_requires_url(self) -> None:
        """Strategy should require URL."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="",
            source="website",
            description="",
        )

        contact = self.strategy.discover(job)

        self.assertIsNone(contact)


class RecruiterDiscoveryServiceTests(unittest.TestCase):
    """Test recruiter discovery service."""

    def test_service_uses_default_strategies(self) -> None:
        """Service should use default strategies in order."""
        service = RecruiterDiscoveryService()

        self.assertEqual(len(service.strategies), 4)
        self.assertEqual(service.strategies[0].name, "greenhouse")
        self.assertEqual(service.strategies[1].name, "company_careers_page")
        self.assertEqual(service.strategies[2].name, "company_contact_page")
        self.assertEqual(service.strategies[3].name, "common_address")

    def test_service_uses_custom_strategies(self) -> None:
        """Service should accept custom strategies."""
        strategies = [GreenhouseStrategy()]
        service = RecruiterDiscoveryService(strategies=strategies)

        self.assertEqual(len(service.strategies), 1)

    def test_service_returns_first_match(self) -> None:
        """Service should return after first successful discovery."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.greenhouse.io/jobs/123",
            source="greenhouse",
            description="Contact: contact@techcorp.com",
        )

        service = RecruiterDiscoveryService()
        contact = service.discover(job)

        self.assertIsNotNone(contact)
        self.assertEqual(contact.source, "greenhouse_metadata")

    def test_service_tries_next_strategy_on_failure(self) -> None:
        """Service should try next strategy if first fails."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com/careers",
            source="website",
            description="For careers: careers@techcorp.com",
        )

        service = RecruiterDiscoveryService()
        contact = service.discover(job)

        # Greenhouse should fail (not greenhouse.io), careers page should succeed
        self.assertIsNotNone(contact)

    def test_service_returns_none_if_all_strategies_fail(self) -> None:
        """Service should return None if no strategy succeeds."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="",  # No URL, so common address fails
            source="website",
            description="",  # No description, so other strategies fail
        )

        service = RecruiterDiscoveryService()
        contact = service.discover(job)

        self.assertIsNone(contact)


class RecruiterDiscoveryWorkflowTests(unittest.TestCase):
    """Test recruiter discovery workflow."""

    def setUp(self) -> None:
        """Set up test database and workflow."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.database = SQLiteDatabase(self.db_path)
        self.job_repository = JobRepository(self.database)
        self.workflow = RecruiterDiscoveryWorkflow(
            database=self.database,
            job_repository=self.job_repository,
        )

    def tearDown(self) -> None:
        """Clean up test database."""
        self.database.close()
        self.temp_dir.cleanup()

    def test_workflow_discovers_recruiters(self) -> None:
        """Workflow should discover recruiters for recommended jobs."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.greenhouse.io/jobs/123",
            source="greenhouse",
            description="Contact: contact@techcorp.com",
            status="RECOMMENDED",
        )
        self.job_repository.insert_jobs([job])

        result = self.workflow.run()

        self.assertEqual(result["recommended_jobs"], 1)
        self.assertEqual(result["recruiters_found"], 1)

        # Verify stored in database
        jobs = self.job_repository.find_rows_by_status("RECOMMENDED")
        self.assertEqual(jobs[0]["recruiter_email"], "contact@techcorp.com")

    def test_workflow_skips_already_discovered(self) -> None:
        """Workflow should skip jobs with existing recruiter."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com/careers",
            source="website",
            status="RECOMMENDED",
        )
        self.job_repository.insert_jobs([job])

        # Manually set recruiter
        self.job_repository.update_recruiter(
            job_id="job1",
            email="existing@techcorp.com",
            name="Existing",
            source="manual",
            confidence=100,
        )

        result = self.workflow.run()

        self.assertEqual(result["already_discovered"], 1)
        self.assertEqual(result["recruiters_found"], 0)

    def test_workflow_ignores_non_recommended_jobs(self) -> None:
        """Workflow should only process RECOMMENDED jobs."""
        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.com/careers",
            source="website",
            status="NEW",
        )
        self.job_repository.insert_jobs([job])

        result = self.workflow.run()

        self.assertEqual(result["recommended_jobs"], 0)
        self.assertEqual(result["recruiters_found"], 0)

    def test_workflow_logs_statistics(self) -> None:
        """Workflow should return execution statistics."""
        result = self.workflow.run()

        self.assertIn("recommended_jobs", result)
        self.assertIn("already_discovered", result)
        self.assertIn("recruiters_found", result)
        self.assertIn("recruiters_missing", result)
        self.assertIn("execution_time", result)

    def test_workflow_with_no_recommended_jobs(self) -> None:
        """Workflow should handle no recommended jobs gracefully."""
        result = self.workflow.run()

        self.assertEqual(result["recommended_jobs"], 0)
        self.assertEqual(result["recruiters_found"], 0)
        self.assertEqual(result["execution_time"], 0.0)


class DiscoveryStrategyOrderTests(unittest.TestCase):
    """Test that strategies are ordered by confidence and priority."""

    def test_strategy_ordering_by_confidence(self) -> None:
        """Strategies should be ordered by confidence."""
        strategies = [
            GreenhouseStrategy(),  # 85
            CompanyCareersPageStrategy(),  # 70
            CompanyContactPageStrategy(),  # 65
            CommonAddressStrategy(),  # 40
        ]

        job = Job(
            id="job1",
            title="Backend Engineer",
            company="TechCorp",
            location="Remote",
            url="https://techcorp.greenhouse.io/jobs/123",
            source="greenhouse",
            description="Contact: contact@techcorp.com for careers: careers@techcorp.com",
        )

        # Greenhouse should match first
        service = RecruiterDiscoveryService(strategies=strategies)
        contact = service.discover(job)

        self.assertIsNotNone(contact)
        self.assertEqual(contact.source, "greenhouse_metadata")


class StrategyInterfaceTests(unittest.TestCase):
    """Test that all strategies implement the interface correctly."""

    def test_all_strategies_have_discover_method(self) -> None:
        """All strategies should have discover method."""
        strategies = [
            GreenhouseStrategy(),
            CompanyCareersPageStrategy(),
            CompanyContactPageStrategy(),
            CommonAddressStrategy(),
        ]

        for strategy in strategies:
            self.assertTrue(hasattr(strategy, "discover"))
            self.assertTrue(callable(strategy.discover))

    def test_all_strategies_have_name_property(self) -> None:
        """All strategies should have name property."""
        strategies = [
            GreenhouseStrategy(),
            CompanyCareersPageStrategy(),
            CompanyContactPageStrategy(),
            CommonAddressStrategy(),
        ]

        for strategy in strategies:
            self.assertTrue(hasattr(strategy, "name"))
            self.assertIsInstance(strategy.name, str)
            self.assertGreater(len(strategy.name), 0)


if __name__ == "__main__":
    unittest.main()
