"""Manual Gmail OAuth login utility.

Run this on a local development machine to generate or replace token.json.
Do not run this script on a headless VPS.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.application.gmail.client import GmailAuthError, GmailClient
from app.application.gmail.config import GmailConfig
from config.settings import Settings


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> int:
    _configure_logging()
    logger = logging.getLogger("gmail_login")

    try:
        settings = Settings.load()
        gmail_config = GmailConfig.load(settings)
        client = GmailClient(gmail_config)

        logger.info("Starting interactive Gmail OAuth login")
        logger.info("OAuth client path: %s", gmail_config.client_secret_path)
        logger.info("Token output path: %s", gmail_config.token_path)

        client.authenticate_interactive()

        logger.info("Gmail OAuth login completed successfully")
        logger.info("Token saved to: %s", gmail_config.token_path)
        return 0
    except GmailAuthError as exc:
        logger.error("Gmail OAuth login failed: %s", exc)
        return 1
    except Exception as exc:
        logger.error("Unexpected failure during Gmail OAuth login: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
