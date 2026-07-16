"""Application notes extraction."""
from __future__ import annotations

from app.application.notes.base import NotesProvider
from app.application.notes.default import DefaultNotesProvider
from app.application.notes.greenhouse import GreenhouseNotesProvider
from app.application.notes.remoteok import RemoteOKNotesProvider
from app.application.notes.service import ApplicationNotesService

__all__ = [
    "NotesProvider",
    "RemoteOKNotesProvider",
    "GreenhouseNotesProvider",
    "DefaultNotesProvider",
    "ApplicationNotesService",
]
