"""Gmail OAuth client — handles authentication and service construction only."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from core.exceptions import ApplicationError
from utils.filesystem import ensure_directory

if TYPE_CHECKING:
    from app.application.gmail.config import GmailConfig

logger = logging.getLogger("job_automation")


class GmailAuthError(ApplicationError):
    """Raised when Gmail authentication fails."""


class GmailReauthRequiredError(GmailAuthError):
    """Raised when token re-authentication is required and must be done manually."""


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

    AUTH_STATE_VALID = "VALID"
    AUTH_STATE_REFRESHED = "REFRESHED"
    AUTH_STATE_REAUTH_REQUIRED = "REAUTH_REQUIRED"
    AUTH_STATE_FAILED = "FAILED"

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

        credentials = self._resolve_credentials(interactive=False)
        service = build("gmail", "v1", credentials=credentials)
        logger.info("Gmail authentication: %s", self.AUTH_STATE_VALID)
        logger.info("Gmail client initialized")
        return service

    @staticmethod
    def _needs_refresh(creds) -> bool:
        """Check if credentials need refresh (expired, near-expiry, or unknown expiry)."""
        import datetime

        if creds.expired:
            return True
        # If expiry wasn't parsed from file, token may silently be expired
        if creds.expiry is None:
            return True
        # Proactively refresh if token expires within 5 minutes
        now = datetime.datetime.utcnow()
        if hasattr(creds.expiry, "tzinfo") and creds.expiry.tzinfo is not None:
            import datetime as dt
            now = datetime.datetime.now(dt.timezone.utc)
        if creds.expiry - now < datetime.timedelta(minutes=5):
            return True
        return False

    def _resolve_credentials(self, interactive: bool = False):
        """Load, refresh, or obtain fresh OAuth credentials.

        Returns:
            Valid Google OAuth credentials

        Raises:
            GmailAuthError: On any unrecoverable auth failure
        """
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

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
                logger.error("Gmail authentication: %s", self.AUTH_STATE_FAILED)
                raise GmailAuthError(f"Failed to load OAuth token: {exc}") from exc

        # --- Refresh expired or near-expiry token ---
        if creds and creds.refresh_token and self._needs_refresh(creds):
            try:
                creds.refresh(Request())
                logger.info("Gmail authentication: %s", self.AUTH_STATE_REFRESHED)
                logger.info("OAuth token refreshed successfully")
                self._save_token(creds, token_path)
            except RefreshError as exc:
                logger.error(
                    "OAuth token refresh failed: %s. Refresh token may be invalid or revoked. "
                    "If your Google Cloud project is in 'Testing' mode, refresh tokens expire "
                    "after 7 days. Publish the app to 'Production' in Google Cloud Console "
                    "(OAuth consent screen) to get non-expiring refresh tokens.",
                    exc,
                )
                logger.error("Gmail authentication: %s", self.AUTH_STATE_REAUTH_REQUIRED)
                raise GmailReauthRequiredError(
                    "Gmail re-authentication required: refresh token is invalid or revoked. "
                    "If your app is in 'Testing' mode on Google Cloud, refresh tokens expire after 7 days. "
                    "Fix: publish app to 'Production' in OAuth consent screen, then re-run gmail_login.py."
                ) from exc

        # --- Handle missing/invalid credentials ---
        if not creds:
            if interactive:
                creds = self._run_oauth_flow(token_path)
            else:
                logger.error("Gmail authentication: %s", self.AUTH_STATE_REAUTH_REQUIRED)
                raise GmailReauthRequiredError(
                    "No Gmail OAuth token found. Run local manual login to generate token.json "
                    "and upload it to production."
                )

        if creds and creds.expired and not creds.refresh_token:
            logger.error("Gmail authentication: %s", self.AUTH_STATE_REAUTH_REQUIRED)
            raise GmailReauthRequiredError(
                "Gmail OAuth token is expired and has no refresh token. "
                "Run local manual login to regenerate token.json."
            )

        if creds and not creds.valid:
            if interactive:
                creds = self._run_oauth_flow(token_path)
            else:
                logger.error("Gmail authentication: %s", self.AUTH_STATE_REAUTH_REQUIRED)
                raise GmailReauthRequiredError(
                    "Gmail OAuth token is invalid and cannot be used non-interactively. "
                    "Run local manual login to regenerate token.json."
                )

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
            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
                include_granted_scopes="true",
            )
        except Exception as exc:
            logger.error("Gmail authentication: %s", self.AUTH_STATE_FAILED)
            raise GmailAuthError(f"OAuth browser flow failed: {exc}") from exc

        self._save_token(creds, token_path)
        logger.info("Gmail authentication: %s", self.AUTH_STATE_VALID)
        return creds

    def authenticate_interactive(self) -> None:
        """Run interactive OAuth flow and persist token for later non-interactive use."""
        self._resolve_credentials(interactive=True)

    @staticmethod
    def _save_token(creds, token_path: Path) -> None:
        """Persist OAuth token to disk.

        Args:
            creds: Credentials to persist
            token_path: Destination file path
        """
        temp_path: Path | None = None
        try:
            ensure_directory(token_path.parent)
            token_data = creds.to_json()

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(token_path.parent),
                prefix=f".{token_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_file.write(token_data)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)

            os.replace(temp_path, token_path)
            logger.info("OAuth token saved to %s", token_path)
        except Exception as exc:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            # Non-fatal: next run will just re-authenticate
            logger.warning("Failed to save OAuth token: %s", exc)
