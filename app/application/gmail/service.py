"""Gmail draft service — builds MIME messages and creates drafts only."""
from __future__ import annotations

import base64
import logging
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING

from core.exceptions import ApplicationError

if TYPE_CHECKING:
    from app.application.gmail.client import GmailClient
    from app.application.models import Application

logger = logging.getLogger("job_automation")


class GmailDraftError(ApplicationError):
    """Raised when draft creation fails."""


class GmailDraftService:
    """Create Gmail drafts from Application objects.

    Responsibilities:
    - Validate required inputs before touching the API
    - Build a standards-compliant MIME message (RFC 2822)
    - Attach the candidate resume
    - Base64-URL-safe encode for Gmail API
    - Call users().drafts().create() and return the Draft ID

    Authentication is entirely delegated to GmailClient.
    No auth logic lives here.
    """

    def __init__(self, client: GmailClient) -> None:
        """Initialize draft service.

        Args:
            client: Authenticated GmailClient instance
        """
        self._client = client

    @staticmethod
    def _combine_body_and_notes(body: str, notes: str) -> str:
        """Combine email body with application notes section.

        The notes are appended with a clear delimiter so the user can:
        - Review the opportunity details
        - Reference the job URL and recruiter info
        - Delete the notes section before sending

        Args:
            body: Email body text
            notes: Application notes text

        Returns:
            Combined body with notes appended
        """
        return f"{body}\n\n{notes}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_draft_from_application(
        self,
        application: Application,
    ) -> str:
        """Build a MIME message from an Application and create a Gmail draft.

        Combines email body with application notes for user reference.

        Args:
            application: Fully populated Application object

        Returns:
            Gmail Draft ID

        Raises:
            GmailDraftError: On validation failure or API error
        """
        # Combine body and notes with clear delimiter
        combined_body = self._combine_body_and_notes(
            body=application.email_body,
            notes=application.application_notes,
        )

        return self.create_draft(
            to_email=application.recipient_email,
            subject=application.email_subject,
            body=combined_body,
            resume_path=application.resume_path,
        )

    def create_draft(
        self,
        to_email: str | None,
        subject: str,
        body: str,
        resume_path: Path,
    ) -> str:
        """Build a MIME message and create a Gmail draft.

        Args:
            to_email: Recipient email address, or None to leave the To field empty
            subject: Email subject line
            body: Plain-text email body (may include notes section)
            resume_path: Path to resume PDF to attach

        Returns:
            Gmail Draft ID

        Raises:
            GmailDraftError: On validation failure or API error
        """
        self._validate(subject=subject, body=body, resume_path=resume_path)

        raw_message = self._build_mime_message(
            to_email=to_email,
            subject=subject,
            body=body,
            resume_path=resume_path,
        )

        return self._call_api(raw_message, to_email=to_email, subject=subject)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(subject: str, body: str, resume_path: Path) -> None:
        """Validate all inputs before touching Gmail API.

        Args:
            subject: Email subject
            body: Email body
            resume_path: Path to resume file

        Raises:
            GmailDraftError: If any required input is missing or invalid
        """
        if not subject or not subject.strip():
            raise GmailDraftError("Email subject is missing or empty")
        if not body or not body.strip():
            raise GmailDraftError("Email body is missing or empty")
        if not resume_path:
            raise GmailDraftError("Resume path is required")
        if not Path(resume_path).exists():
            raise GmailDraftError(f"Resume file not found: {resume_path}")

    @staticmethod
    def _build_mime_message(
        to_email: str | None,
        subject: str,
        body: str,
        resume_path: Path,
    ) -> str:
        """Build a Base64-URL-safe encoded MIME message for the Gmail API.

        Uses Python's EmailMessage (RFC 6532) which the Gmail API accepts.

        Args:
            to_email: Recipient address, or None
            subject: Subject line
            body: Plain text body
            resume_path: Resume file to attach

        Returns:
            Base64-URL-safe encoded MIME string

        Raises:
            GmailDraftError: If the attachment cannot be read
        """
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["To"] = to_email or ""
        msg.set_content(body)

        try:
            resume_data = Path(resume_path).read_bytes()
        except OSError as exc:
            raise GmailDraftError(f"Failed to read resume attachment: {exc}") from exc

        msg.add_attachment(
            resume_data,
            maintype="application",
            subtype="pdf",
            filename=Path(resume_path).name,
        )
        logger.debug("Resume attached: %s (%d bytes)", Path(resume_path).name, len(resume_data))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return raw

    def _call_api(self, raw_message: str, to_email: str | None, subject: str) -> str:
        """Submit the encoded message to the Gmail drafts API.

        Args:
            raw_message: Base64-URL-safe encoded MIME message
            to_email: Recipient address (for logging only)
            subject: Subject line (for logging only)

        Returns:
            Gmail Draft ID

        Raises:
            GmailDraftError: On API failure
        """
        try:
            from googleapiclient.errors import HttpError
        except ImportError as exc:
            raise GmailDraftError(
                "Google API client library not installed. "
                "Run: pip install google-api-python-client"
            ) from exc

        try:
            service = self._client.get_service()
            result = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw_message}})
                .execute()
            )
        except HttpError as exc:
            raise GmailDraftError(
                f"Gmail API error {exc.status_code}: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise GmailDraftError(f"Draft creation failed: {exc}") from exc

        draft_id: str = result["id"]
        # logger.info(
        #     "Draft created successfully — id=%s to=%s subject=%s",
        #     draft_id,
        #     to_email or "(empty)",
        #     subject[:60],
        # )
        return draft_id
