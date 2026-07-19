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
        self.assertEqual(settings.database_path, project_root() / "shared" / "database" / "jobs.db")
        self.assertEqual(settings.resume_directory, project_root() / "shared" / "resumes")
        self.assertEqual(settings.gmail_oauth_client, project_root() / "config" / "gmail_oauth_client.json")
        self.assertEqual(settings.gmail_token, project_root() / "shared" / "oauth" / "token.json")
        self.assertEqual(settings.log_directory, project_root() / "shared" / "logs")
        self.assertEqual(settings.openai_api_key, "")

    def test_settings_overrides_values_from_environment(self) -> None:
        settings = Settings(
            env={
                "LOG_LEVEL": "DEBUG",
                "SQLITE_DATABASE": "custom/db.sqlite3",
                "RESUME_DIRECTORY": "custom/resumes",
                "GMAIL_OAUTH_CLIENT": "secrets/oauth_client.json",
                "GMAIL_TOKEN": "secrets/token.json",
                "LOG_DIRECTORY": "runtime/logs",
                "OPENAI_API_KEY": "test-key",
            }
        )

        self.assertEqual(settings.log_level, "DEBUG")
        self.assertEqual(settings.database_path, project_root() / "custom" / "db.sqlite3")
        self.assertEqual(settings.resume_directory, project_root() / "custom" / "resumes")
        self.assertEqual(settings.gmail_oauth_client, project_root() / "secrets" / "oauth_client.json")
        self.assertEqual(settings.gmail_token, project_root() / "secrets" / "token.json")
        self.assertEqual(settings.log_directory, project_root() / "runtime" / "logs")
        self.assertEqual(settings.openai_api_key, "test-key")

    def test_settings_keeps_absolute_paths_unchanged(self) -> None:
        settings = Settings(
            env={
                "SQLITE_DATABASE": "C:/runtime/jobs.db",
                "RESUME_DIRECTORY": "C:/runtime/resumes",
                "GMAIL_OAUTH_CLIENT": "C:/runtime/oauth_client.json",
                "GMAIL_TOKEN": "C:/runtime/token.json",
                "LOG_DIRECTORY": "C:/runtime/logs",
            }
        )

        self.assertEqual(settings.database_path, Path("C:/runtime/jobs.db"))
        self.assertEqual(settings.resume_directory, Path("C:/runtime/resumes"))
        self.assertEqual(settings.gmail_oauth_client, Path("C:/runtime/oauth_client.json"))
        self.assertEqual(settings.gmail_token, Path("C:/runtime/token.json"))
        self.assertEqual(settings.log_directory, Path("C:/runtime/logs"))


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
