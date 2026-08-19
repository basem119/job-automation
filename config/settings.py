from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from core.exceptions import ConfigurationError
from utils.filesystem import ensure_directory, project_root

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_SQLITE_DATABASE = "shared/database/jobs.db"
DEFAULT_RESUME_DIRECTORY = "shared/resumes"
DEFAULT_GMAIL_OAUTH_CLIENT = "shared/oauth/gmail_oauth_client.json"
DEFAULT_GMAIL_TOKEN = "shared/oauth/token.json"
DEFAULT_LOG_DIRECTORY = "shared/logs"


class Settings:
    """Application settings loaded from the environment and .env file."""

    _WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/].*")

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        load_dotenv(project_root() / ".env", override=False)
        env = env if env is not None else os.environ
        merged_env = {**os.environ, **dict(env)}

        self.log_level = self._read_setting(merged_env, "LOG_LEVEL", DEFAULT_LOG_LEVEL)
        self.database_path = self._read_path_setting(
            merged_env,
            "SQLITE_DATABASE",
            DEFAULT_SQLITE_DATABASE,
        )
        self.resume_directory = self._read_path_setting(
            merged_env,
            "RESUME_DIRECTORY",
            DEFAULT_RESUME_DIRECTORY,
        )
        self.gmail_oauth_client = self._read_path_setting(
            merged_env,
            "GMAIL_OAUTH_CLIENT",
            DEFAULT_GMAIL_OAUTH_CLIENT,
        )
        self.gmail_token = self._read_path_setting(
            merged_env,
            "GMAIL_TOKEN",
            DEFAULT_GMAIL_TOKEN,
        )
        self.log_directory = self._read_path_setting(
            merged_env,
            "LOG_DIRECTORY",
            DEFAULT_LOG_DIRECTORY,
        )
        self.enable_remoteok = self._read_bool_setting(merged_env, "ENABLE_REMOTEOK", True)
        self.enable_greenhouse = self._read_bool_setting(merged_env, "ENABLE_GREENHOUSE", True)
        self.enable_adzuna = self._read_bool_setting(
            merged_env,
            "ADZUNA_ENABLED",
            self._read_bool_setting(merged_env, "ENABLE_ADZUNA", False),
        )
        self.enable_jobicy = self._read_bool_setting(
            merged_env,
            "JOBICY_ENABLED",
            self._read_bool_setting(merged_env, "ENABLE_JOBICY", False),
        )
        self.adzuna_app_id = self._read_optional_setting(merged_env, "ADZUNA_APP_ID")
        self.adzuna_app_key = self._read_optional_setting(merged_env, "ADZUNA_APP_KEY")
        self.adzuna_country = self._read_setting(merged_env, "ADZUNA_COUNTRY", "us").lower()
        self.openai_api_key = self._read_optional_setting(merged_env, "OPENAI_API_KEY")

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
        return self._resolve_path(raw_value)

    @staticmethod
    def _resolve_path(raw_value: str) -> Path:
        path = Path(raw_value)
        if path.is_absolute() or Settings._WINDOWS_ABSOLUTE_PATH_PATTERN.match(raw_value):
            return path
        return project_root() / path

    def _validate_mandatory_values(self) -> None:
        missing = []
        if not self.log_level:
            missing.append("LOG_LEVEL")
        if not self.database_path:
            missing.append("SQLITE_DATABASE")
        if not self.resume_directory:
            missing.append("RESUME_DIRECTORY")
        if not self.gmail_oauth_client:
            missing.append("GMAIL_OAUTH_CLIENT")
        if not self.gmail_token:
            missing.append("GMAIL_TOKEN")
        if not self.log_directory:
            missing.append("LOG_DIRECTORY")

        if missing:
            raise ConfigurationError(
                f"Missing mandatory configuration values: {', '.join(missing)}"
            )

    def validate_runtime_paths(self) -> None:
        """Validate and prepare runtime filesystem resources required at startup."""
        if not self.gmail_oauth_client.exists() or not self.gmail_oauth_client.is_file():
            raise ConfigurationError(
                "Gmail OAuth client JSON not found: "
                f"{self.gmail_oauth_client} (GMAIL_OAUTH_CLIENT)"
            )

        if not self.resume_directory.exists() or not self.resume_directory.is_dir():
            raise ConfigurationError(
                "Resume directory not found: "
                f"{self.resume_directory} (RESUME_DIRECTORY)"
            )

        ensure_directory(self.database_path.parent)
        ensure_directory(self.gmail_token.parent)
        ensure_directory(self.log_directory)

    @classmethod
    def load(cls) -> "Settings":
        return cls()
