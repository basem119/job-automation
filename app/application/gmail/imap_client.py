"""Gmail IMAP client — creates drafts via IMAP using App Password."""
from __future__ import annotations

import imaplib
import logging
import ssl

from core.exceptions import ApplicationError

logger = logging.getLogger("job_automation")


class GmailImapError(ApplicationError):
    """Raised when IMAP operations fail."""


class GmailImapClient:
    """Create Gmail drafts via IMAP APPEND using App Password.

    No OAuth, no token expiry. Requires:
    - 2-Step Verification enabled on the Google account
    - An App Password generated at https://myaccount.google.com/apppasswords

    Environment variables:
    - GMAIL_ADDRESS: The Gmail address
    - GMAIL_APP_PASSWORD: The 16-character App Password
    """

    IMAP_HOST = "imap.gmail.com"
    IMAP_PORT = 993
    DRAFTS_FOLDER_CANDIDATES = ["[Gmail]/Drafts", "[Google Mail]/Drafts", "Drafts"]

    def __init__(self, email: str, app_password: str) -> None:
        if not email or not app_password:
            raise GmailImapError(
                "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set. "
                "Generate an App Password at https://myaccount.google.com/apppasswords"
            )
        self._email = email
        self._app_password = app_password
        self._connection: imaplib.IMAP4_SSL | None = None
        self._drafts_folder: str | None = None

    @property
    def email(self) -> str:
        return self._email

    def connect(self) -> None:
        """Establish IMAP connection and authenticate."""
        try:
            ctx = ssl.create_default_context()
            self._connection = imaplib.IMAP4_SSL(
                self.IMAP_HOST, self.IMAP_PORT, ssl_context=ctx
            )
            self._connection.login(self._email, self._app_password)
            logger.info("IMAP authenticated as %s", self._email)
        except imaplib.IMAP4.error as exc:
            raise GmailImapError(
                f"IMAP authentication failed: {exc}. "
                "Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
            ) from exc
        except Exception as exc:
            raise GmailImapError(f"IMAP connection failed: {exc}") from exc

        self._drafts_folder = self._detect_drafts_folder()

    def _detect_drafts_folder(self) -> str:
        """Detect the correct Drafts folder name via LIST with \\Drafts flag."""
        status, folders = self._connection.list()
        if status == "OK" and folders:
            for item in folders:
                decoded = item.decode() if isinstance(item, bytes) else str(item)
                if "\\Drafts" in decoded:
                    # Format: (\\HasNoChildren \\Drafts) "/" "[Gmail]/Drafts"
                    parts = decoded.split('" "')
                    if len(parts) == 2:
                        return parts[1].strip('"')
                    parts = decoded.split("\" \"")
                    if len(parts) == 2:
                        return parts[1].strip('"')

        # Fallback: try known candidates
        for candidate in self.DRAFTS_FOLDER_CANDIDATES:
            status, _ = self._connection.select(f'"{candidate}"')
            if status == "OK":
                self._connection.close()
                logger.info("Drafts folder detected: %s", candidate)
                return candidate

        raise GmailImapError(
            "Could not detect Gmail Drafts folder. "
            "None of the known folder names exist."
        )

    def append_draft(self, mime_bytes: bytes) -> str:
        """Append a MIME message to Gmail Drafts folder.

        Args:
            mime_bytes: Raw MIME message bytes

        Returns:
            IMAP UID of the created draft

        Raises:
            GmailImapError: On IMAP failure
        """
        if self._connection is None:
            self.connect()

        folder = self._drafts_folder

        try:
            status, response = self._connection.append(
                f'"{folder}"',
                "\\Draft",
                None,
                mime_bytes,
            )
        except (imaplib.IMAP4.error, OSError) as exc:
            # Reconnect once on connection drop
            logger.warning("IMAP append failed, reconnecting: %s", exc)
            self.connect()
            folder = self._drafts_folder
            status, response = self._connection.append(
                f'"{folder}"',
                "\\Draft",
                None,
                mime_bytes,
            )

        if status != "OK":
            raise GmailImapError(f"IMAP APPEND failed: {status} {response}")

        # Extract UID from response like [b'[APPENDUID 1 12345] ...']
        uid = self._extract_uid(response)
        return uid

    @staticmethod
    def _extract_uid(response) -> str:
        """Extract UID from IMAP APPEND response."""
        if response and response[0]:
            text = response[0].decode() if isinstance(response[0], bytes) else str(response[0])
            # Format: [APPENDUID <uidvalidity> <uid>] (Success)
            if "APPENDUID" in text:
                parts = text.split()
                for i, part in enumerate(parts):
                    if part == "[APPENDUID" and i + 2 < len(parts):
                        return parts[i + 2].rstrip("]")
        return "imap-draft"

    def disconnect(self) -> None:
        """Close IMAP connection."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None
