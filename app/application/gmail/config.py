"""Gmail OAuth configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config.settings import Settings

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"


@dataclass
class GmailConfig:
    """Configuration for Gmail OAuth integration."""

    client_secret_path: Path
    token_path: Path
    scopes: list[str] = field(default_factory=lambda: [GMAIL_COMPOSE_SCOPE])

    @classmethod
    def load(cls, settings: Settings | None = None) -> "GmailConfig":
        """Load Gmail configuration from application settings.

        Returns:
            GmailConfig instance with configured paths
        """
        runtime_settings = settings or Settings.load()
        return cls(
            client_secret_path=runtime_settings.gmail_oauth_client,
            token_path=runtime_settings.gmail_token,
        )
