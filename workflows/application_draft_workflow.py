"""Application draft generation workflow."""
from __future__ import annotations

import json
import logging

from app.application.builder import ApplicationBuilder
from app.application.gmail.client import GmailAuthError, GmailClient
from app.application.gmail.config import GmailConfig
from app.application.gmail.service import GmailDraftError, GmailDraftService
from app.recruiter.models import RecruiterContact
from app.recruiter.service import RecruiterDiscoveryService
from config.profile import Profile
from config.settings import Settings
from domain.job import Job
from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class ApplicationDraftWorkflow:
    """Generate Gmail drafts for every recommended job that has no draft yet."""

    def __init__(
        self,
        repository: JobRepository,
        settings: Settings | None = None,
        gmail_config: GmailConfig | None = None,
    ) -> None:
        """Initialize workflow.

        Args:
            repository: Job repository
            settings: Loaded application settings
            gmail_config: Gmail OAuth configuration. Defaults to settings-backed config.
        """
        self.repository = repository
        self.settings = settings or Settings.load()
        self.gmail_config = gmail_config or GmailConfig.load(self.settings)
        self.builder = ApplicationBuilder(settings=self.settings)
        self.recruiter_service = RecruiterDiscoveryService()

        client = GmailClient(self.gmail_config)
        self.gmail_service = GmailDraftService(client)
        logger.info(
            "ApplicationDraftWorkflow ready (client_secret=%s, token=%s)",
            self.gmail_config.client_secret_path,
            self.gmail_config.token_path,
        )

    def run(self) -> dict:
        """Execute draft generation workflow.

        Returns:
            Statistics dict
        """
        stats = {
            "recommended_jobs": 0,
            "already_have_draft": 0,
            "recruiter_discovery_attempted": 0,
            "recruiter_discovery_found": 0,
            "applications_built": 0,
            "drafts_created": 0,
            "drafts_with_recipient": 0,
            "drafts_without_recipient": 0,
            "validation_failures": 0,
            "draft_failures": 0,
        }

        try:
            profile = Profile.load()
        except Exception as exc:
            logger.error("Failed to load profile: %s", exc)
            return stats

        rows = self.repository.find_rows_by_status("RECOMMENDED")
        stats["recommended_jobs"] = len(rows)

        if not rows:
            logger.info("No recommended jobs found - skipping draft generation")
            return stats

        logger.info("Processing %d recommended jobs for draft creation", len(rows))

        for row in rows:
            self._process_row(row, profile, stats)

        self._log_statistics(stats)
        return stats

    def _process_row(self, row, profile, stats: dict) -> None:
        """Process one database row: build application and create draft."""
        job_id = row["job_id"]

        if "draft_id" in row.keys() and row["draft_id"]:
            logger.debug("Job %s already has a draft - skipping", job_id)
            stats["already_have_draft"] += 1
            return

        job = self._row_to_job(row)
        recruiter_contact = self._resolve_recruiter(row, job, stats)

        recommendation_score = None
        if "recommendation_score" in row.keys():
            try:
                recommendation_score = int(row["recommendation_score"]) if row["recommendation_score"] else None
            except (ValueError, TypeError):
                recommendation_score = None
        
        matched_skills = None
        if "matched_skills" in row.keys() and row["matched_skills"]:
            try:
                matched_skills = json.loads(row["matched_skills"])
            except (json.JSONDecodeError, TypeError):
                matched_skills = None

        missing_skills = None
        if "missing_skills" in row.keys() and row["missing_skills"]:
            try:
                missing_skills = json.loads(row["missing_skills"])
            except (json.JSONDecodeError, TypeError):
                missing_skills = None

        application = self.builder.build(
            job,
            profile,
            recruiter_contact=recruiter_contact,
            recommendation_score=recommendation_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
        )
        if not application:
            logger.warning("Failed to build application for job %s", job_id)
            stats["validation_failures"] += 1
            return

        stats["applications_built"] += 1

        try:
            draft_id = self.gmail_service.create_draft_from_application(application)
        except GmailDraftError as exc:
            logger.error("Draft creation failed for job %s: %s", job_id, exc)
            stats["draft_failures"] += 1
            return
        except GmailAuthError as exc:
            logger.error("Gmail authentication failed: %s", exc)
            stats["draft_failures"] += 1
            return

        processing_notes = f"Recipient: {application.recipient_email or 'EMPTY'}"
        self.repository.update_draft(job_id, draft_id, processing_notes)
        logger.info("Draft ID stored for job %s: %s", job_id, draft_id)

        stats["drafts_created"] += 1
        if application.recipient_email:
            stats["drafts_with_recipient"] += 1
        else:
            stats["drafts_without_recipient"] += 1

    def _resolve_recruiter(self, row, job: Job, stats: dict) -> RecruiterContact | None:
        """Return recruiter contact from DB or attempt live discovery."""
        recruiter_email = (
            row["recruiter_email"]
            if "recruiter_email" in row.keys() and row["recruiter_email"]
            else None
        )

        if recruiter_email:
            return RecruiterContact(
                email=recruiter_email,
                name=row["recruiter_name"] if "recruiter_name" in row.keys() else "",
                source=row["recruiter_source"] if "recruiter_source" in row.keys() else "database",
                confidence=row["recruiter_confidence"] if "recruiter_confidence" in row.keys() else 0,
            )

        stats["recruiter_discovery_attempted"] += 1
        try:
            contact = self.recruiter_service.discover(job)
            if contact:
                stats["recruiter_discovery_found"] += 1
                self.repository.update_recruiter(
                    job.id,
                    contact.email,
                    contact.name,
                    contact.source,
                    contact.confidence,
                )
                return contact
        except Exception as exc:
            logger.warning(
                "Recruiter discovery failed for job %s (non-blocking): %s", job.id, exc
            )

        return None

    @staticmethod
    def _row_to_job(row) -> Job:
        """Convert a sqlite3.Row to a Job domain object."""
        technologies = None
        if "technologies" in row.keys() and row["technologies"]:
            try:
                technologies = json.loads(row["technologies"])
            except (json.JSONDecodeError, TypeError):
                technologies = None

        return Job(
            id=str(row["job_id"]),
            title=row["title"],
            company=row["company"],
            location=row["location"],
            description=row["description"] or "",
            url=row["url"],
            source=row["source"],
            published_at=row["published_at"] if "published_at" in row.keys() else None,
            status=row["status"] if "status" in row.keys() else "RECOMMENDED",
            technologies=technologies,
        )

    @staticmethod
    def _log_statistics(stats: dict) -> None:
        logger.info(
            "Application Draft Workflow Statistics:\n"
            "  Recommended jobs:              %d\n"
            "  Already have draft (skipped):  %d\n"
            "  Recruiter discovery attempted: %d\n"
            "  Recruiter discovery found:     %d\n"
            "  Applications built:            %d\n"
            "  Drafts created:                %d\n"
            "    With recipient:              %d\n"
            "    Without recipient:           %d\n"
            "  Validation failures:           %d\n"
            "  Draft failures:                %d",
            stats["recommended_jobs"],
            stats["already_have_draft"],
            stats["recruiter_discovery_attempted"],
            stats["recruiter_discovery_found"],
            stats["applications_built"],
            stats["drafts_created"],
            stats["drafts_with_recipient"],
            stats["drafts_without_recipient"],
            stats["validation_failures"],
            stats["draft_failures"],
        )
