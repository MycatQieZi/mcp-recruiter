"""Extensions base — abstract interface for candidate type handlers.

Used to extend the system to support API, Agent, Skill types in the future.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.enums import CandidateType
from ..core.models import JobDescription, Resume, TestResult


class CandidateTypeHandler(ABC):
    """Abstract handler for a specific candidate type."""

    @property
    @abstractmethod
    def candidate_type(self) -> CandidateType:
        ...

    @abstractmethod
    def detect(self, raw_metadata: dict) -> bool:
        """Can this handler process this raw candidate data?"""
        ...

    @abstractmethod
    def build_resume(self, raw_metadata: dict) -> Resume:
        """Generate a standardized resume from raw metadata."""
        ...

    @abstractmethod
    def score_capabilities(self, resume: Resume, job: JobDescription) -> float:
        """Type-specific capability scoring."""
        ...
