from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    """Generic job model shared across collectors and the storage layer."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Job identifier from the upstream source")
    title: str = Field(..., description="Human-readable role title")
    company: str = Field(..., description="Company name")
    location: str = Field(..., description="Job location")
    description: str = Field(default="", description="Job description text")
    url: str = Field(..., description="Canonical job URL")
    source: str = Field(..., description="Source system name")
    published_at: datetime | None = Field(default=None, description="Job publish timestamp")
    salary: str | None = Field(default=None, description="Salary or compensation text")
    technologies: list[str] | None = Field(default=None, description="Skills or technologies")
    normalized_location: str | None = Field(default=None, description="Normalized location")
    description_text: str | None = Field(default=None, description="Normalized description text")
