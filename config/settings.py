from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from core.exceptions import ConfigurationError
from utils.filesystem import project_root

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_DATABASE_PATH = "data/jobs.db"


class Settings:
    """Application settings loaded from the environment and .env file."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        load_dotenv(project_root() / ".env", override=False)
        env = env if env is not None else os.environ
        merged_env = {**os.environ, **dict(env)}

        self.log_level = self._read_setting(merged_env, "LOG_LEVEL", DEFAULT_LOG_LEVEL)
        self.database_path = self._read_path_setting(
            merged_env,
            "DATABASE_PATH",
            DEFAULT_DATABASE_PATH,
        )
        self.enable_remoteok = self._read_bool_setting(merged_env, "ENABLE_REMOTEOK", True)
        self.enable_greenhouse = self._read_bool_setting(merged_env, "ENABLE_GREENHOUSE", True)
        self.openai_api_key = self._read_optional_setting(merged_env, "OPENAI_API_KEY")
        self.google_client_id = self._read_optional_setting(merged_env, "GOOGLE_CLIENT_ID")
        self.google_client_secret = self._read_optional_setting(merged_env, "GOOGLE_CLIENT_SECRET")
        self.gmail_refresh_token = self._read_optional_setting(merged_env, "GMAIL_REFRESH_TOKEN")

        self._validate_mandatory_values()

    def _read_setting(self, env: Mapping[str, str], name: str, default: str) -> str:
        value = env.get(name)
        if value is None or value == "":
            return default
        return value.strip()

    def _read_optional_setting(self, env: Mapping[str, str], name: str) -> str:
        value = env.get(name)
        if value is None:
            return ""
        return value.strip()

    def _read_bool_setting(self, env: Mapping[str, str], name: str, default: bool) -> bool:
        value = self._read_setting(env, name, str(default).lower())
        normalized = value.strip().lower()

        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

        return default

    def _read_path_setting(self, env: Mapping[str, str], name: str, default: str) -> Path:
        raw_value = self._read_setting(env, name, default)
        return Path(raw_value)

    def _validate_mandatory_values(self) -> None:
        missing = []
        if not self.log_level:
            missing.append("LOG_LEVEL")
        if not self.database_path:
            missing.append("DATABASE_PATH")

        if missing:
            raise ConfigurationError(
                f"Missing mandatory configuration values: {', '.join(missing)}"
            )

    @classmethod
    def load(cls) -> "Settings":
        return cls()
