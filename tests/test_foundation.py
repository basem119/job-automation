import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings
from core.version import version
from utils.filesystem import ensure_directory, ensure_file, project_root


class SettingsTests(unittest.TestCase):
    def test_settings_uses_defaults_when_values_are_missing(self) -> None:
        settings = Settings(env={})

        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.database_path, Path("data/jobs.db"))
        self.assertEqual(settings.openai_api_key, "")
        self.assertEqual(settings.google_client_id, "")
        self.assertEqual(settings.google_client_secret, "")
        self.assertEqual(settings.gmail_refresh_token, "")

    def test_settings_overrides_values_from_environment(self) -> None:
        settings = Settings(
            env={
                "LOG_LEVEL": "DEBUG",
                "DATABASE_PATH": "custom/db.sqlite3",
                "OPENAI_API_KEY": "test-key",
                "GOOGLE_CLIENT_ID": "google-id",
                "GOOGLE_CLIENT_SECRET": "google-secret",
                "GMAIL_REFRESH_TOKEN": "gmail-token",
            }
        )

        self.assertEqual(settings.log_level, "DEBUG")
        self.assertEqual(settings.database_path, Path("custom/db.sqlite3"))
        self.assertEqual(settings.openai_api_key, "test-key")
        self.assertEqual(settings.google_client_id, "google-id")
        self.assertEqual(settings.google_client_secret, "google-secret")
        self.assertEqual(settings.gmail_refresh_token, "gmail-token")


class FilesystemTests(unittest.TestCase):
    def test_ensure_directory_creates_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "logs"

            created = ensure_directory(target)

            self.assertTrue(created.exists())
            self.assertTrue(created.is_dir())

    def test_ensure_file_creates_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "nested" / "example.txt"

            created = ensure_file(target, content="hello")

            self.assertTrue(created.exists())
            self.assertEqual(created.read_text(encoding="utf-8"), "hello")


class VersionTests(unittest.TestCase):
    def test_version_is_exposed(self) -> None:
        self.assertEqual(version, "0.1.0")


class ProjectRootTests(unittest.TestCase):
    def test_project_root_points_to_repository_root(self) -> None:
        self.assertEqual(project_root().name, "job-automation")


if __name__ == "__main__":
    unittest.main()
