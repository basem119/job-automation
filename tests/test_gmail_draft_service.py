from __future__ import annotations

import base64
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path

from app.application.gmail.service import DraftCreationResult, GmailDraftService


class _FakeDraftRequest:
    def __init__(self, draft_id: str) -> None:
        self._draft_id = draft_id

    def execute(self) -> dict:
        return {"id": self._draft_id}


class _FakeDraftsApi:
    def __init__(self) -> None:
        self.last_body: dict | None = None

    def create(self, userId: str, body: dict):
        self.last_body = body
        return _FakeDraftRequest("draft-123")


class _FakeUsersApi:
    def __init__(self, drafts_api: _FakeDraftsApi) -> None:
        self._drafts_api = drafts_api

    def drafts(self) -> _FakeDraftsApi:
        return self._drafts_api


class _FakeGmailServiceApi:
    def __init__(self) -> None:
        self.drafts_api = _FakeDraftsApi()
        self.users_api = _FakeUsersApi(self.drafts_api)

    def users(self) -> _FakeUsersApi:
        return self.users_api


class _FakeClient:
    def __init__(self) -> None:
        self.service = _FakeGmailServiceApi()

    def get_service(self):
        return self.service


class GmailDraftServiceHeaderSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.resume_path = Path(self.temp_dir.name) / "resume.pdf"
        self.resume_path.write_bytes(b"%PDF-1.4\n% fake pdf")
        self.fake_client = _FakeClient()
        self.service = GmailDraftService(self.fake_client)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _parse_last_message(self):
        raw = self.fake_client.service.drafts_api.last_body["message"]["raw"]
        decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
        return BytesParser(policy=policy.default).parsebytes(decoded)

    def test_valid_recipient_sets_to_header(self) -> None:
        result = self.service.create_draft(
            to_email="recruiter@example.com",
            subject="Application for Backend Engineer",
            body="Body",
            resume_path=self.resume_path,
        )

        self.assertIsInstance(result, DraftCreationResult)
        self.assertEqual(result.recipient_email, "recruiter@example.com")

        msg = self._parse_last_message()
        self.assertEqual(msg["To"], "recruiter@example.com")

    def test_missing_recipient_none_creates_draft_without_recipient(self) -> None:
        result = self.service.create_draft(
            to_email=None,
            subject="Application for Backend Engineer",
            body="Body",
            resume_path=self.resume_path,
        )

        self.assertIsNone(result.recipient_email)
        msg = self._parse_last_message()
        self.assertEqual(msg["To"], "")

    def test_missing_recipient_empty_string_creates_draft_without_recipient(self) -> None:
        result = self.service.create_draft(
            to_email="",
            subject="Application for Backend Engineer",
            body="Body",
            resume_path=self.resume_path,
        )

        self.assertIsNone(result.recipient_email)
        msg = self._parse_last_message()
        self.assertEqual(msg["To"], "")

    def test_recipient_with_surrounding_whitespace_is_normalized(self) -> None:
        result = self.service.create_draft(
            to_email="  recruiter@example.com  ",
            subject="Application for Backend Engineer",
            body="Body",
            resume_path=self.resume_path,
        )

        self.assertEqual(result.recipient_email, "recruiter@example.com")
        msg = self._parse_last_message()
        self.assertEqual(msg["To"], "recruiter@example.com")

    def test_recipient_with_carriage_return_is_ignored_safely(self) -> None:
        with self.assertLogs("job_automation", level="WARNING") as logs:
            result = self.service.create_draft(
                to_email="recruiter@example.com\r",
                subject="Application for Backend Engineer",
                body="Body",
                resume_path=self.resume_path,
            )

        self.assertIsNone(result.recipient_email)
        msg = self._parse_last_message()
        self.assertEqual(msg["To"], "")
        self.assertIn("Invalid draft recipient ignored", "\n".join(logs.output))

    def test_recipient_with_line_feed_is_ignored_safely(self) -> None:
        with self.assertLogs("job_automation", level="WARNING") as logs:
            result = self.service.create_draft(
                to_email="recruiter@example.com\n",
                subject="Application for Backend Engineer",
                body="Body",
                resume_path=self.resume_path,
            )

        self.assertIsNone(result.recipient_email)
        msg = self._parse_last_message()
        self.assertEqual(msg["To"], "")
        self.assertIn("Invalid draft recipient ignored", "\n".join(logs.output))

    def test_subject_with_crlf_is_sanitized_before_header_assignment(self) -> None:
        result = self.service.create_draft(
            to_email="recruiter@example.com",
            subject="Application for Backend Engineer\r\n",
            body="Body",
            resume_path=self.resume_path,
        )

        self.assertEqual(result.recipient_email, "recruiter@example.com")
        msg = self._parse_last_message()
        self.assertEqual(msg["Subject"], "Application for Backend Engineer")
        self.assertNotIn("\r", msg["Subject"])
        self.assertNotIn("\n", msg["Subject"])

    def test_malformed_recipient_is_treated_as_missing(self) -> None:
        with self.assertLogs("job_automation", level="WARNING") as logs:
            result = self.service.create_draft(
                to_email="not-an-email",
                subject="Application for Backend Engineer",
                body="Body",
                resume_path=self.resume_path,
            )

        self.assertIsNone(result.recipient_email)
        msg = self._parse_last_message()
        self.assertEqual(msg["To"], "")
        self.assertIn("Invalid draft recipient ignored", "\n".join(logs.output))
