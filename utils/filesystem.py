from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the repository root for the application."""
    return Path(__file__).resolve().parents[1]


def ensure_directory(path: Path) -> Path:
    """Create a directory if it is missing and return the normalized path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def ensure_file(path: Path, content: str = "") -> Path:
    """Create a file with optional content if it is missing and return the path."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if not file_path.exists():
        file_path.write_text(content, encoding="utf-8")
    return file_path


def validate_required_directories() -> None:
    """Validate startup directories required for the current milestone."""
    from config.settings import Settings

    logs_dir = Settings.load().log_directory
    ensure_directory(logs_dir)
