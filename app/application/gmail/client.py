"""Gmail OAuth client — handles authentication and service construction only."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from core.exceptions import ApplicationError
from utils.filesystem import ensure_directory

if TYPE_CHECKING:
    from app.application.gmail.config import GmailConfig

logger = logging.getLogger("job_automation")


class GmailAuthError(ApplicationError):
    """Raised when Gmail authentication fails."""


class GmailClient:
    """Authenticate with Gmail via OAuth Desktop flow and build the API service.

    Responsibilities:
    - Load OAuth client secret
    - Load persisted OAuth token
    - Refresh expired tokens automatically
    - Run browser-based OAuth flow when no token exists
    - Build and return an authenticated Gmail API service

    No business logic lives here.
    """

    def __init__(self, config: GmailConfig) -> None:
        """Initialize Gmail client.

        Args:
            config: Gmail OAuth configuration (paths and scopes)
        """
        self.config = config
        self._service = None

    def get_service(self):
        """Return authenticated Gmail API service (lazy, cached).

        Returns:
            Authenticated Gmail API service

        Raises:
            GmailAuthError: If authentication cannot be established
        """
        if self._service is None:
            self._service = self._build_service()
        return self._service

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_service(self):
        """Build authenticated Gmail service."""
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GmailAuthError(
                "Google API client library not installed. "
                "Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            ) from exc

        credentials = self._resolve_credentials()
        service = build("gmail", "v1", credentials=credentials)
        logger.info("Gmail client initialized (account: %s)", credentials.token_uri)
        return service

    def _resolve_credentials(self):
        """Load, refresh, or obtain fresh OAuth credentials.

        Returns:
            Valid Google OAuth credentials

        Raises:
            GmailAuthError: On any unrecoverable auth failure
        """
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds: Credentials | None = None

        # --- Load persisted token ---
        token_path = self.config.token_path
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(token_path), self.config.scopes
                )
                logger.info("OAuth token loaded from %s", token_path)
            except Exception as exc:
                logger.warning("Failed to load OAuth token: %s — will re-authenticate", exc)
                creds = None

        # --- Refresh expired token ---
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("OAuth token refreshed successfully")
                self._save_token(creds, token_path)
            except RefreshError as exc:
                logger.warning("OAuth token refresh failed: %s — will re-authenticate", exc)
                creds = None

        # --- Run browser OAuth flow ---
        if not creds or not creds.valid:
            creds = self._run_oauth_flow(token_path)

        return creds

    def _run_oauth_flow(self, token_path: Path):
        """Run interactive OAuth browser flow and persist token.

        Args:
            token_path: Where to save the resulting token

        Returns:
            Valid Google OAuth credentials

        Raises:
            GmailAuthError: If client secret is missing or flow fails
        """
        from google_auth_oauthlib.flow import InstalledAppFlow

        client_secret = self.config.client_secret_path
        if not client_secret.exists():
            raise GmailAuthError(
                f"OAuth client secret not found: {client_secret}. "
                "Download it from Google Cloud Console → APIs & Services → Credentials."
            )

        logger.info("OAuth browser authentication required — opening browser")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret), self.config.scopes
            )
            creds = flow.run_local_server(port=0)
        except Exception as exc:
            raise GmailAuthError(f"OAuth browser flow failed: {exc}") from exc

        self._save_token(creds, token_path)
        return creds

    @staticmethod
    def _save_token(creds, token_path: Path) -> None:
        """Persist OAuth token to disk.

        Args:
            creds: Credentials to persist
            token_path: Destination file path
        """
        try:
            ensure_directory(token_path.parent)
            token_path.write_text(creds.to_json(), encoding="utf-8")
            logger.info("OAuth token saved to %s", token_path)
        except Exception as exc:
            # Non-fatal: next run will just re-authenticate
            logger.warning("Failed to save OAuth token: %s", exc)
