from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from app.application.gmail.client import GmailAuthError, GmailClient, GmailReauthRequiredError
from app.application.gmail.config import GmailConfig


class FakeRefreshError(Exception):
    """Fake Google RefreshError for tests."""


class FakeRequest:
    """Fake Google auth request transport."""


class FakeCredentials:
    """Test double for google.oauth2.credentials.Credentials."""

    next_loaded_credentials = None
    load_exception: Exception | None = None

    def __init__(
        self,
        *,
        valid: bool,
        expired: bool,
        refresh_token: str | None,
        refresh_exception: Exception | None = None,
        token_json: str = '{"token": "value"}',
        expiry=None,
    ) -> None:
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refresh_exception = refresh_exception
        self.token_json = token_json
        self.expiry = expiry

    @classmethod
    def from_authorized_user_file(cls, _path: str, _scopes: list[str]):
        if cls.load_exception:
            raise cls.load_exception
        if cls.next_loaded_credentials is None:
            raise ValueError("No fake credentials configured")
        return cls.next_loaded_credentials

    def refresh(self, _request: FakeRequest) -> None:
        if self.refresh_exception is not None:
            raise self.refresh_exception
        self.expired = False
        self.valid = True

    def to_json(self) -> str:
        return self.token_json


class FakeInstalledAppFlow:
    """Test double for google_auth_oauthlib.flow.InstalledAppFlow."""

    returned_credentials = FakeCredentials(valid=True, expired=False, refresh_token="refresh")

    @classmethod
    def from_client_secrets_file(cls, _path: str, _scopes: list[str]):
        return cls()

    def run_local_server(self, **_kwargs):
        return self.returned_credentials


class GmailOAuthTests(unittest.TestCase):
    def _stub_google_modules(self):
        google_mod = types.ModuleType("google")
        google_auth_mod = types.ModuleType("google.auth")
        google_auth_ex_mod = types.ModuleType("google.auth.exceptions")
        google_auth_ex_mod.RefreshError = FakeRefreshError
        google_auth_transport_mod = types.ModuleType("google.auth.transport")
        google_auth_transport_requests_mod = types.ModuleType("google.auth.transport.requests")
        google_auth_transport_requests_mod.Request = FakeRequest

        google_oauth2_mod = types.ModuleType("google.oauth2")
        google_oauth2_credentials_mod = types.ModuleType("google.oauth2.credentials")
        google_oauth2_credentials_mod.Credentials = FakeCredentials

        google_auth_oauthlib_mod = types.ModuleType("google_auth_oauthlib")
        google_auth_oauthlib_flow_mod = types.ModuleType("google_auth_oauthlib.flow")
        google_auth_oauthlib_flow_mod.InstalledAppFlow = FakeInstalledAppFlow

        return patch.dict(
            sys.modules,
            {
                "google": google_mod,
                "google.auth": google_auth_mod,
                "google.auth.exceptions": google_auth_ex_mod,
                "google.auth.transport": google_auth_transport_mod,
                "google.auth.transport.requests": google_auth_transport_requests_mod,
                "google.oauth2": google_oauth2_mod,
                "google.oauth2.credentials": google_oauth2_credentials_mod,
                "google_auth_oauthlib": google_auth_oauthlib_mod,
                "google_auth_oauthlib.flow": google_auth_oauthlib_flow_mod,
            },
            clear=False,
        )

    @staticmethod
    def _build_client(tmp_dir: Path) -> tuple[GmailClient, Path, Path]:
        client_secret = tmp_dir / "gmail_oauth_client.json"
        token_path = tmp_dir / "token.json"
        config = GmailConfig(client_secret_path=client_secret, token_path=token_path)
        return GmailClient(config), client_secret, token_path

    def setUp(self) -> None:
        FakeCredentials.next_loaded_credentials = None
        FakeCredentials.load_exception = None

    def test_valid_existing_credentials_are_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, _client_secret, token_path = self._build_client(tmp_dir)
            token_path.write_text("{}", encoding="utf-8")

            loaded = FakeCredentials(valid=True, expired=False, refresh_token="refresh")
            FakeCredentials.next_loaded_credentials = loaded

            with self._stub_google_modules():
                creds = client._resolve_credentials(interactive=False)

            self.assertIs(creds, loaded)

    def test_expired_access_token_refreshes_and_persists_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, _client_secret, token_path = self._build_client(tmp_dir)
            token_path.write_text("{}", encoding="utf-8")

            refreshed_payload = '{"token": "refreshed"}'
            loaded = FakeCredentials(
                valid=False,
                expired=True,
                refresh_token="refresh",
                token_json=refreshed_payload,
            )
            FakeCredentials.next_loaded_credentials = loaded

            with self._stub_google_modules(), self.assertLogs("job_automation", level="INFO") as logs:
                creds = client._resolve_credentials(interactive=False)

            self.assertIs(creds, loaded)
            self.assertEqual(token_path.read_text(encoding="utf-8"), refreshed_payload)
            self.assertIn("Gmail authentication: REFRESHED", "\n".join(logs.output))

    def test_invalid_grant_during_refresh_requires_reauth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, _client_secret, token_path = self._build_client(tmp_dir)
            token_path.write_text("{}", encoding="utf-8")

            loaded = FakeCredentials(
                valid=False,
                expired=True,
                refresh_token="refresh",
                refresh_exception=FakeRefreshError("invalid_grant: Bad Request"),
            )
            FakeCredentials.next_loaded_credentials = loaded

            with self._stub_google_modules(), self.assertLogs("job_automation", level="ERROR") as logs, patch.object(
                client,
                "_run_oauth_flow",
                side_effect=AssertionError("Browser flow must not run during unattended invalid_grant"),
            ):
                with self.assertRaises(GmailReauthRequiredError):
                    client._resolve_credentials(interactive=False)

            self.assertIn("Gmail authentication: REAUTH_REQUIRED", "\n".join(logs.output))

    def test_missing_token_file_requires_reauth_without_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, _client_secret, _token_path = self._build_client(tmp_dir)

            with self._stub_google_modules(), patch.object(
                client,
                "_run_oauth_flow",
                side_effect=AssertionError("Browser flow should not run in headless mode"),
            ):
                with self.assertRaises(GmailReauthRequiredError):
                    client._resolve_credentials(interactive=False)

    def test_missing_oauth_client_file_fails_interactive_login(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, client_secret, _token_path = self._build_client(tmp_dir)
            self.assertFalse(client_secret.exists())

            with self._stub_google_modules():
                with self.assertRaises(GmailAuthError):
                    client.authenticate_interactive()

    def test_expired_token_without_refresh_token_requires_reauth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, _client_secret, token_path = self._build_client(tmp_dir)
            token_path.write_text("{}", encoding="utf-8")

            loaded = FakeCredentials(valid=False, expired=True, refresh_token=None)
            FakeCredentials.next_loaded_credentials = loaded

            with self._stub_google_modules(), self.assertLogs("job_automation", level="ERROR") as logs:
                with self.assertRaises(GmailReauthRequiredError):
                    client._resolve_credentials(interactive=False)

            self.assertIn("Gmail authentication: REAUTH_REQUIRED", "\n".join(logs.output))

    def test_corrupt_token_file_reports_failed_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, _client_secret, token_path = self._build_client(tmp_dir)
            token_path.write_text("not-json", encoding="utf-8")
            FakeCredentials.load_exception = ValueError("bad token payload")

            with self._stub_google_modules(), self.assertLogs("job_automation", level="ERROR") as logs:
                with self.assertRaises(GmailAuthError):
                    client._resolve_credentials(interactive=False)

            self.assertIn("Gmail authentication: FAILED", "\n".join(logs.output))

    def test_atomic_persistence_preserves_existing_token_on_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            client, _client_secret, token_path = self._build_client(tmp_dir)
            token_path.write_text('{"token": "old"}', encoding="utf-8")

            loaded = FakeCredentials(
                valid=False,
                expired=True,
                refresh_token="refresh",
                token_json='{"token": "new"}',
            )
            FakeCredentials.next_loaded_credentials = loaded

            with self._stub_google_modules(), patch.object(os, "replace", side_effect=OSError("disk error")), self.assertLogs(
                "job_automation", level="WARNING"
            ) as logs:
                creds = client._resolve_credentials(interactive=False)

            self.assertIs(creds, loaded)
            self.assertEqual(token_path.read_text(encoding="utf-8"), '{"token": "old"}')
            self.assertIn("Failed to save OAuth token", "\n".join(logs.output))

            temp_candidates = list(token_path.parent.glob(f".{token_path.name}.*.tmp"))
            self.assertEqual(temp_candidates, [])


if __name__ == "__main__":
    unittest.main()
