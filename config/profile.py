"""Load, validate, and provide access to candidate profile from YAML."""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.exceptions import ApplicationError
from utils.filesystem import project_root


@dataclass
class AvailabilityProfile:
    """Candidate availability constraints."""

    notice_period_days: int = 30
    remote_preference: str = "preferred"  # preferred, acceptable, onsite
    hybrid_preference: str = "preferred"  # preferred, acceptable, onsite
    relocation_willing: bool = False


@dataclass
class SkillsProfile:
    """Candidate skills organized by dynamic categories."""

    categories: dict[str, list[str]] = field(default_factory=dict)

    def get(self, category: str) -> list[str]:
        """Get skills in a category (case-insensitive).
        
        Args:
            category: Category name
            
        Returns:
            List of skills in category, empty list if not found
        """
        category_lower = category.lower()
        for key, values in self.categories.items():
            if key.lower() == category_lower:
                return values or []
        return []

    def all_skills(self) -> list[str]:
        """Get all skills deduplicated, trimmed, and lowercase.
        
        Returns:
            Sorted list of unique skills across all categories
        """
        all_skills_set = set()
        for skills in self.categories.values():
            if skills:
                for skill in skills:
                    if isinstance(skill, str):
                        trimmed = skill.strip().lower()
                        if trimmed:
                            all_skills_set.add(trimmed)
        return sorted(all_skills_set)

    def category_names(self) -> list[str]:
        """Get all category names in sorted order.
        
        Returns:
            Sorted list of category names
        """
        return sorted(self.categories.keys())

    def primary_skills(self) -> list[str]:
        """Get primary skills (from 'core' or 'primary' category if it exists).
        
        Returns:
            List of primary skills
        """
        # Try 'core' first, then 'primary'
        for category in ["core", "primary"]:
            skills = self.get(category)
            if skills:
                return skills
        # If no core/primary, return all skills from first category
        if self.categories:
            first_category = self.category_names()[0]
            return self.get(first_category)
        return []

    def has_skill(self, skill: str) -> bool:
        """Check if skill exists in any category (case-insensitive).
        
        Args:
            skill: Skill name to check
            
        Returns:
            True if skill found
        """
        skill_lower = skill.lower().strip()
        return skill_lower in self.all_skills()

    def has_category(self, category: str) -> bool:
        """Check if category exists (case-insensitive).
        
        Args:
            category: Category name to check
            
        Returns:
            True if category exists
        """
        return bool(self.get(category))


@dataclass
class ExperienceProfile:
    """Candidate experience summary."""

    years: int
    summary: str = ""


@dataclass
class Profile:
    """Complete candidate profile with optional metadata."""

    name: str
    title: str
    location: str
    experience: ExperienceProfile
    skills: SkillsProfile
    certifications: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    availability: AvailabilityProfile = field(default_factory=AvailabilityProfile)
    
    # Additional sections
    strengths: list[str] = field(default_factory=list)
    preferred_domains: list[str] = field(default_factory=list)
    preferred_roles: list[str] = field(default_factory=list)
    resume_profiles: dict[str, str] = field(default_factory=dict)
    career_goals: dict[str, Any] = field(default_factory=dict)
    
    # Store any additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, profile_path: str | Path | None = None) -> Profile:
        """Load profile from YAML file.
        
        Args:
            profile_path: Path to profile.yaml. If None, uses default 
                         project_root()/config/profile.yaml
        
        Returns:
            Loaded Profile instance
            
        Raises:
            FileNotFoundError: If profile file not found
            ValueError: If profile YAML is invalid or missing required fields
            ApplicationError: If profile validation fails
        """
        if profile_path is None:
            profile_path = project_root() / "config" / "profile.yaml"
        else:
            profile_path = Path(profile_path)

        if not profile_path.exists():
            raise FileNotFoundError(f"Profile not found: {profile_path}")

        try:
            with open(profile_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in profile: {exc}") from exc

        if not data:
            raise ValueError("Profile YAML is empty")

        # Validate required fields
        cls._validate_required(data)

        # Extract experience
        exp_data = data.get("experience", {})
        experience = ExperienceProfile(
            years=exp_data.get("years", 0),
            summary=data.get("summary", ""),
        )

        # Extract skills - now dynamic categories
        skills_data = data.get("skills", {})
        skills = SkillsProfile(categories=dict(skills_data))

        # Extract availability
        avail_data = data.get("availability", {})
        availability = AvailabilityProfile(
            notice_period_days=avail_data.get("notice_period_days", 30),
            remote_preference=avail_data.get("remote_preference", "preferred"),
            hybrid_preference=avail_data.get("hybrid_preference", "preferred"),
            relocation_willing=avail_data.get("relocation_willing", False),
        )

        # Create profile
        profile = cls(
            name=data.get("name", ""),
            title=data.get("title", ""),
            location=data.get("location", ""),
            experience=experience,
            skills=skills,
            certifications=data.get("certifications", []),
            languages=data.get("languages", []),
            availability=availability,
            strengths=data.get("strengths", []),
            preferred_domains=data.get("preferred_domains", []),
            preferred_roles=data.get("preferred_roles", []),
            resume_profiles=data.get("resume_profiles", {}),
            career_goals=data.get("career_goals", {}),
        )

        # Store any additional metadata not explicitly mapped
        known_keys = {
            "name", "title", "location", "experience", "summary",
            "skills", "certifications", "languages", "availability",
            "strengths", "preferred_domains", "preferred_roles",
            "resume_profiles", "career_goals"
        }
        for key, value in data.items():
            if key not in known_keys:
                profile.metadata[key] = value

        return profile

    @staticmethod
    def _validate_required(data: dict) -> None:
        """Validate that required fields are present.
        
        Args:
            data: Profile data dictionary
            
        Raises:
            ValueError: If required fields missing
            ApplicationError: If validation fails
        """
        required_fields = ["name", "title", "experience"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise ValueError(f"Profile missing required fields: {', '.join(missing)}")

        # Validate experience.years
        exp_data = data.get("experience", {})
        if not isinstance(exp_data, dict) or "years" not in exp_data:
            raise ValueError("Profile experience must have 'years' field")

        years = exp_data.get("years")
        if not isinstance(years, int) or years < 0:
            raise ValueError("Profile experience.years must be a non-negative integer")

        # Validate skills exist and is a dict
        if "skills" not in data:
            raise ValueError("Profile must have 'skills' section")
        
        skills_data = data.get("skills", {})
        if not isinstance(skills_data, dict):
            raise ValueError("Profile skills must be a dictionary")
        
        if not skills_data:
            raise ValueError("Profile skills must not be empty")

    def primary_skills(self) -> list[str]:
        """Get primary skills from the skills profile.
        
        Returns:
            List of primary skills
        """
        return self.skills.primary_skills()

    def has_skill(self, skill: str) -> bool:
        """Check if candidate has a specific skill.
        
        Args:
            skill: Skill name to check
            
        Returns:
            True if skill found in profile
        """
        return self.skills.has_skill(skill)

    def has_category(self, category: str) -> bool:
        """Check if candidate has a skill category.
        
        Args:
            category: Category name to check
            
        Returns:
            True if category exists
        """
        return self.skills.has_category(category)

    def resume(self, profile_name: str) -> str | None:
        """Get resume filename for a profile name.
        
        Args:
            profile_name: Resume profile name (e.g., 'backend', 'devops')
            
        Returns:
            Resume filename or None if not found
        """
        return self.resume_profiles.get(profile_name)

    def summary_for_ai(self) -> str:
        """Generate a concise, structured summary for AI provider prompts.
        
        Returns:
            Formatted text representation suitable for AI consumption
        """
        lines = []
        lines.append(f"Candidate Profile: {self.name}")
        lines.append(f"Title: {self.title}")
        lines.append(f"Location: {self.location}")
        lines.append(f"Experience: {self.experience.years} years")
        
        if self.experience.summary:
            lines.append(f"\nSummary:")
            lines.append(self.experience.summary)

        lines.append(f"\nSkill Categories:")
        for category in self.skills.category_names():
            skills = self.skills.get(category)
            if skills:
                skills_str = ", ".join(skills)
                lines.append(f"  {category}: {skills_str}")

        if self.strengths:
            lines.append(f"\nStrengths:")
            for strength in self.strengths:
                lines.append(f"  - {strength}")

        if self.preferred_roles:
            lines.append(f"\nPreferred Roles:")
            for role in self.preferred_roles[:3]:  # Top 3
                lines.append(f"  - {role}")

        if self.preferred_domains:
            lines.append(f"\nPreferred Domains:")
            for domain in self.preferred_domains[:3]:  # Top 3
                lines.append(f"  - {domain}")

        if self.languages:
            lines.append(f"\nLanguages: {', '.join(self.languages)}")

        return "\n".join(lines)
