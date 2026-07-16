"""Email template handling."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from config.profile import Profile
from domain.job import Job

if TYPE_CHECKING:
    pass


class EmailTemplate:
    """Generate professional email body from templates."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize with template directory.
        
        Args:
            template_dir: Directory containing email templates (defaults to app/application/templates)
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = Path(template_dir)
        self.template_file = self.template_dir / "application_email.txt"

    def generate(self, job: Job, profile: Profile) -> str:
        """Generate professional email body.

        Args:
            job: Job posting
            profile: Candidate profile

        Returns:
            Professional email body text
        """
        # If template exists, use it
        if self.template_file.exists():
            return self._generate_from_template(job, profile)
        
        # Otherwise, generate inline
        return self._generate_default(job, profile)

    def _generate_from_template(self, job: Job, profile: Profile) -> str:
        """Generate from template file with placeholder replacement.
        
        Args:
            job: Job posting
            profile: Candidate profile
            
        Returns:
            Email body with placeholders replaced
        """
        template_text = self.template_file.read_text(encoding="utf-8")

        # Replace placeholders
        placeholders = {
            "{candidate_name}": profile.name,
            "{company}": job.company,
            "{role}": job.title,
            "{experience_years}": str(profile.experience.years),
            "{primary_skills}": ", ".join(profile.primary_skills()),
            "{location}": job.location,
        }

        body = template_text
        for placeholder, value in placeholders.items():
            body = body.replace(placeholder, str(value).strip())

        return body.strip()

    def _generate_default(self, job: Job, profile: Profile) -> str:
        """Generate default email body without template.
        
        Args:
            job: Job posting
            profile: Candidate profile
            
        Returns:
            Professional email body
        """
        primary_skills = ", ".join(profile.primary_skills()) if profile.primary_skills() else "relevant skills"

        body = f"""Dear Hiring Team,

I am writing to express my strong interest in the {job.title} position at {job.company}.

With {profile.experience.years} years of experience in backend development and software engineering, I am confident that my skills and expertise align well with your requirements. I have a strong background in {primary_skills}, and I am passionate about building scalable, maintainable systems.

I am excited about the opportunity to contribute to your team and would welcome the chance to discuss how my experience can add value to {job.company}. I am available to discuss this position at your convenience.

Thank you for considering my application. I look forward to hearing from you.

Best regards,
{profile.name}"""

        return body
