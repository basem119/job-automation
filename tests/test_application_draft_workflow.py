from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.application.gmail.service import DraftCreationResult, GmailDraftError
from config.settings import Settings
from domain.job import Job
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository
from workflows.application_draft_workflow import ApplicationDraftWorkflow


class _FakeBuilder:
    def __init__(self) -> None:
        self.fail_build_for_job_ids: set[str] = set()

    def build(self, job, profile, recruiter_contact=None, **kwargs):
        if job.id in self.fail_build_for_job_ids:
            return None

        recipient = recruiter_contact.email if recruiter_contact else None
        return SimpleNamespace(
            job_id=job.id,
            recipient_email=recipient,
            email_subject=f"Application {job.id}",
            email_body="Hello",
            application_notes="NOTES",
            resume_path=Path(__file__),
        )


class _FakeRecruiterService:
    def discover(self, job):
        return None


class _FakeGmailService:
    def __init__(self) -> None:
        self.fail_with_draft_error_for_job_ids: set[str] = set()
        self.fail_with_unexpected_for_job_ids: set[str] = set()
        self.calls: list[str] = []

    def create_draft_from_application(self, application):
        job_id = application.job_id
        self.calls.append(job_id)

        if job_id in self.fail_with_draft_error_for_job_ids:
            raise GmailDraftError("simulated draft failure")
        if job_id in self.fail_with_unexpected_for_job_ids:
            raise RuntimeError("simulated unexpected failure")

        return DraftCreationResult(
            draft_id=f"draft-{job_id}",
            recipient_email=application.recipient_email,
        )


class ApplicationDraftWorkflowIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.database = SQLiteDatabase(self.db_path)
        self.repository = JobRepository(self.database)

        self.workflow = ApplicationDraftWorkflow(
            repository=self.repository,
            settings=Settings.load(),
        )

        self.fake_builder = _FakeBuilder()
        self.fake_recruiter = _FakeRecruiterService()
        self.fake_gmail = _FakeGmailService()

        self.workflow.builder = self.fake_builder
        self.workflow.recruiter_service = self.fake_recruiter
        self.workflow.gmail_service = self.fake_gmail

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def _insert_recommended_job(self, job_id: str, title: str = "Backend Engineer") -> None:
        job = Job(
            id=job_id,
            title=title,
            company="ExampleCo",
            location="Remote",
            description="Role",
            url=f"https://example.com/{job_id}",
            source="test",
            status="RECOMMENDED",
        )
        self.repository.insert_jobs([job])

    def test_one_job_fails_and_others_continue(self) -> None:
        self._insert_recommended_job("job-1")
        self._insert_recommended_job("job-2")
        self._insert_recommended_job("job-3")

        self.repository.update_recruiter("job-1", "recruiter1@example.com", "R1", "test", 80)
        self.repository.update_recruiter("job-2", "recruiter2@example.com", "R2", "test", 80)
        self.repository.update_recruiter("job-3", "recruiter3@example.com", "R3", "test", 80)

        self.fake_gmail.fail_with_draft_error_for_job_ids.add("job-2")

        with patch("workflows.application_draft_workflow.Profile.load", return_value=object()):
            stats = self.workflow.run()

        self.assertEqual(stats["recommended_jobs"], 3)
        self.assertEqual(stats["applications_built"], 3)
        self.assertEqual(stats["drafts_created"], 2)
        self.assertEqual(stats["draft_failures"], 1)
        self.assertEqual(stats["drafts_with_recipient"], 2)
        self.assertEqual(stats["drafts_without_recipient"], 0)

        rows = self.repository.find_rows_by_status("RECOMMENDED")
        draft_by_job = {row["job_id"]: row["draft_id"] for row in rows}
        self.assertEqual(draft_by_job["job-1"], "draft-job-1")
        self.assertIsNone(draft_by_job["job-2"])
        self.assertEqual(draft_by_job["job-3"], "draft-job-3")

    def test_all_jobs_fail_finishes_normally(self) -> None:
        self._insert_recommended_job("job-a")
        self._insert_recommended_job("job-b")

        self.fake_gmail.fail_with_draft_error_for_job_ids.update({"job-a", "job-b"})

        with patch("workflows.application_draft_workflow.Profile.load", return_value=object()):
            stats = self.workflow.run()

        self.assertEqual(stats["recommended_jobs"], 2)
        self.assertEqual(stats["applications_built"], 2)
        self.assertEqual(stats["drafts_created"], 0)
        self.assertEqual(stats["draft_failures"], 2)
        self.assertFalse(stats["gmail_auth_failed"])

    def test_existing_draft_is_skipped(self) -> None:
        self._insert_recommended_job("job-skip")
        self._insert_recommended_job("job-new")

        self.repository.update_draft("job-skip", "existing-draft", "Recipient: recruiter@example.com")

        self.repository.update_recruiter("job-new", "recruiter@example.com", "R", "test", 80)

        with patch("workflows.application_draft_workflow.Profile.load", return_value=object()):
            stats = self.workflow.run()

        self.assertEqual(stats["recommended_jobs"], 2)
        self.assertEqual(stats["already_have_draft"], 1)
        self.assertEqual(stats["drafts_created"], 1)
        self.assertEqual(self.fake_gmail.calls, ["job-new"])

    def test_no_recruiter_email_still_creates_draft_without_recipient(self) -> None:
        self._insert_recommended_job("job-no-recipient")

        with patch("workflows.application_draft_workflow.Profile.load", return_value=object()):
            stats = self.workflow.run()

        self.assertEqual(stats["recommended_jobs"], 1)
        self.assertEqual(stats["drafts_created"], 1)
        self.assertEqual(stats["drafts_with_recipient"], 0)
        self.assertEqual(stats["drafts_without_recipient"], 1)

        row = self.repository.find_rows_by_status("RECOMMENDED")[0]
        self.assertEqual(row["draft_id"], "draft-job-no-recipient")

    def test_unexpected_job_error_is_isolated_and_next_job_continues(self) -> None:
        self._insert_recommended_job("job-u1")
        self._insert_recommended_job("job-u2")
        self._insert_recommended_job("job-u3")

        self.fake_gmail.fail_with_unexpected_for_job_ids.add("job-u2")

        with patch("workflows.application_draft_workflow.Profile.load", return_value=object()):
            stats = self.workflow.run()

        self.assertEqual(stats["recommended_jobs"], 3)
        self.assertEqual(stats["drafts_created"], 2)
        self.assertEqual(stats["draft_failures"], 1)

        rows = self.repository.find_rows_by_status("RECOMMENDED")
        draft_by_job = {row["job_id"]: row["draft_id"] for row in rows}
        self.assertEqual(draft_by_job["job-u1"], "draft-job-u1")
        self.assertIsNone(draft_by_job["job-u2"])
        self.assertEqual(draft_by_job["job-u3"], "draft-job-u3")
