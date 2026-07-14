"""Abstract interface for AI providers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from config.profile import Profile
from core.analysis.analysis_result import AnalysisResult
from domain.job import Job


class AIProvider(ABC):
    """Abstract base class for AI providers.
    
    AI providers analyze recommended jobs but do NOT make filtering decisions.
    The recommendation engine remains the source of truth.
    """

    def __init__(self, profile: Profile):
        """Initialize provider with candidate profile.
        
        Args:
            profile: Candidate profile to use for analysis
        """
        self.profile = profile

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'mock', 'openai', 'gemini')."""
        pass

    @abstractmethod
    def analyze(self, job: Job) -> AnalysisResult:
        """Analyze a recommended job.
        
        Args:
            job: Recommended job to analyze
            
        Returns:
            AnalysisResult with match summary, strengths, missing skills, etc.
        """
        pass
