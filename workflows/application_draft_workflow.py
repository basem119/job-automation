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
from domain.job import Job
from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class ApplicationDraftWorkflow:
    """Generate Gmail drafts for every recommended job that has no draft yet."""

    def __init__(
        self,
        repository: JobRepository,
        gmail_config: GmailConfig | None = None,
    ) -> None:
        """Initialize workflow.

        Args:
            repository: Job repository
            gmail_config: Gmail OAuth configuration. Defaults to GmailConfig.load().
        """
        self.repository = repository
        self.gmail_config = gmail_config or GmailConfig.load()
        self.builder = ApplicationBuilder()
        self.recruiter_service = RecruiterDiscoveryService()

        client = GmailClient(self.gmail_config)
        self.gmail_service = GmailDraftService(client)
        logger.info(
            "ApplicationDraftWorkflow ready (client_secret=%s, token=%s)",
            self.gmail_config.client_secret_path,
            self.gmail_config.token_path,
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

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
            logger.info("No recommended jobs found — skipping draft generation")
            return stats

        logger.info("Processing %d recommended jobs for draft creation", len(rows))

        for row in rows:
            self._process_row(row, profile, stats)

        self._log_statistics(stats)
        return stats

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _process_row(self, row, profile, stats: dict) -> None:
        """Process one database row: build application and create draft."""
        job_id = row["job_id"]

        # Duplicate guard
        if "draft_id" in row.keys() and row["draft_id"]:
            logger.debug("Job %s already has a draft — skipping", job_id)
            stats["already_have_draft"] += 1
            return

        job = self._row_to_job(row)

        # Recruiter contact — non-blocking
        recruiter_contact = self._resolve_recruiter(row, job, stats)

        # Extract metadata from row
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

        # Build application with metadata
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

        # Create draft from application
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

        processing_notes = (
            f"Recipient: {application.recipient_email or 'EMPTY'}"
        )
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

        # Live discovery
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

        """Initialize workflow.

        Args:
            repository: Job repository
            resume_dir: Directory containing resumes
            gmail_credentials: Path to Gmail API credentials JSON file
        """
        self.repository = repository
        self.resume_dir = resume_dir
        self.gmail_credentials = gmail_credentials
        self.builder = ApplicationBuilder(template_dir=None)
        
        # Initialize Gmail service with credentials
        if gmail_credentials:
            logger.info(f"Initializing Gmail service with credentials: {gmail_credentials}")
        else:
            logger.info("No Gmail credentials provided, will use mock mode")
        
        self.gmail_service = GmailDraftService(gmail_credentials)
        self.recruiter_service = RecruiterDiscoveryService()

    def run(self) -> dict:
        """Execute draft generation workflow.

        Returns:
            Statistics about workflow execution
        """
        stats = {
            "recommended_jobs": 0,
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
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return stats

        # Get RECOMMENDED jobs without drafts
        recommended_jobs = self.repository.find_rows_by_status("RECOMMENDED")
        stats["recommended_jobs"] = len(recommended_jobs)

        if not recommended_jobs:
            logger.info("No recommended jobs found without drafts")
            return stats

        logger.info(f"Processing {len(recommended_jobs)} recommended jobs for draft creation")

        for job_row in recommended_jobs:
            try:
                # Skip if draft already created
                draft_id = job_row["draft_id"] if "draft_id" in job_row.keys() else None
                if draft_id:
                    logger.debug(f"Job {job_row['job_id']} already has draft, skipping")
                    continue

                # Convert row to Job object
                job = self._row_to_job(job_row)

                # Attempt recruiter discovery if not already done
                recruiter_contact = None
                recruiter_email = job_row["recruiter_email"] if "recruiter_email" in job_row.keys() else None
                if not recruiter_email:
                    stats["recruiter_discovery_attempted"] += 1
                    try:
                        recruiter_contact = self.recruiter_service.discover(job)
                        if recruiter_contact:
                            stats["recruiter_discovery_found"] += 1
                            # Update database with recruiter info
                            self.repository.update_recruiter(
                                job_row["job_id"],
                                recruiter_contact.email,
                                recruiter_contact.name,
                                recruiter_contact.source,
                                recruiter_contact.confidence,
                            )
                    except Exception as e:
                        logger.warning(f"Recruiter discovery failed for job {job.id}: {e}")
                        # Non-blocking: continue to draft creation
                else:
                    # Use existing recruiter info
                    from app.recruiter.models import RecruiterContact

                    recruiter_contact = RecruiterContact(
                        email=recruiter_email,
                        name=job_row["recruiter_name"] if "recruiter_name" in job_row.keys() else "",
                        source=job_row["recruiter_source"] if "recruiter_source" in job_row.keys() else "database",
                        confidence=job_row["recruiter_confidence"] if "recruiter_confidence" in job_row.keys() else 0,
                    )

                # Build application
                application = self.builder.build(job, profile, recruiter_contact)
                if not application:
                    logger.warning(f"Failed to build application for job {job.id}")
                    stats["validation_failures"] += 1
                    continue

                stats["applications_built"] += 1

                # Create Gmail draft
                draft_id = self.gmail_service.create_draft(
                    to_email=application.recipient_email,
                    subject=application.email_subject,
                    body=application.email_body,
                    resume_path=application.resume_path,
                )

                if not draft_id:
                    logger.warning(f"Failed to create draft for job {job.id}")
                    stats["draft_failures"] += 1
                    continue

                # Update database with draft info
                processing_notes = f"Draft created by workflow. Recipient: {application.recipient_email or 'EMPTY'}"
                self.repository.update_draft(job_row["job_id"], draft_id, processing_notes)

                stats["drafts_created"] += 1
                if application.recipient_email:
                    stats["drafts_with_recipient"] += 1
                else:
                    stats["drafts_without_recipient"] += 1

                logger.info(
                    f"Draft created for job {job.id}: {draft_id} "
                    f"(recipient={application.recipient_email or 'EMPTY'})"
                )

            except Exception as e:
                job_id = job_row["job_id"] if "job_id" in job_row.keys() else "unknown"
                logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
                stats["draft_failures"] += 1
                continue

        self._log_statistics(stats)
        return stats

    def _row_to_job(self, row) -> Job:
        """Convert database row to Job object."""
        import json

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

    def _log_statistics(self, stats: dict) -> None:
        """Log workflow statistics."""
        logger.info(
            f"Application Draft Workflow Statistics:\n"
            f"  Recommended jobs: {stats['recommended_jobs']}\n"
            f"  Recruiter discovery attempted: {stats['recruiter_discovery_attempted']}\n"
            f"  Recruiter discovery found: {stats['recruiter_discovery_found']}\n"
            f"  Applications built: {stats['applications_built']}\n"
            f"  Drafts created: {stats['drafts_created']}\n"
            f"  - With recipient: {stats['drafts_with_recipient']}\n"
            f"  - Without recipient: {stats['drafts_without_recipient']}\n"
            f"  Validation failures: {stats['validation_failures']}\n"
            f"  Draft failures: {stats['draft_failures']}"
        )
