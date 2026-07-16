"""Gmail OAuth configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from utils.filesystem import project_root

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"


@dataclass
class GmailConfig:
    """Configuration for Gmail OAuth integration."""

    client_secret_path: Path
    token_path: Path
    scopes: list[str] = field(default_factory=lambda: [GMAIL_COMPOSE_SCOPE])

    @classmethod
    def load(cls) -> "GmailConfig":
        """Load Gmail configuration with project defaults.

        Returns:
            GmailConfig instance with default paths
        """
        root = project_root()
        return cls(
            client_secret_path=root / "config" / "gmail_oauth_client.json",
            token_path=root / "shared" / "oauth" / "token.json",
        )
