"""Extensions base — abstract interface for candidate type handlers.

Used to extend the system to support API, Agent, Skill types in the future.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4

from ..core.enums import CandidateType, RegistrySource
from ..core.models import (
    EcosystemMetrics,
    HealthMetrics,
    JobDescription,
    Resume,
    TestResult,
    ToolSignature,
)
from ..registry.base import RawCandidate


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
    def build_resume_from_candidate(self, candidate: RawCandidate, details: dict | None = None) -> Resume:
        """Generate a standardized resume from a raw candidate."""
        ...

    @abstractmethod
    def score_capabilities(self, resume: Resume, job: JobDescription) -> float:
        """Type-specific capability scoring."""
        ...


class GenericOSSHandler(CandidateTypeHandler):
    """Handler for general open-source project candidates (non-MCP).

    Used for Web Search, Awesome List, PyPI, and other sources that
    discover general open-source projects, libraries, and frameworks.
    """

    @property
    def candidate_type(self) -> CandidateType:
        return CandidateType.API

    def detect(self, raw_metadata: dict) -> bool:
        source = raw_metadata.get("source", "")
        return source in (
            RegistrySource.WEB_SEARCH.value,
            RegistrySource.AWESOME.value,
            RegistrySource.PYPI.value,
        )

    def build_resume_from_candidate(
        self, candidate: RawCandidate, details: dict | None = None
    ) -> Resume:
        """Build a generic Resume from any registry source."""
        import re

        details = details or {}

        # Extract tools/capabilities from description and README
        tools = self._extract_generic_tools(candidate.description, details.get("readme", ""))

        # Extract a pitch
        pitch = candidate.description[:120] if candidate.description else ""
        if len(pitch) == 120:
            pitch += "..."

        # Documentation score
        doc_score = self._score_docs(details.get("readme", ""), candidate.description)

        return Resume(
            id=uuid4(),
            candidate_id=uuid4(),
            display_name=candidate.name,
            one_line_pitch=pitch,
            description=candidate.description,
            candidate_type=CandidateType.API,
            tools_provided=tools,
            resources=[],
            health=HealthMetrics(
                stars=candidate.stars,
                open_issues=candidate.open_issues,
                last_commit_date=candidate.last_updated,
                contributor_count=details.get("contributors_count", 0),
            ),
            ecosystem=EcosystemMetrics(
                dependents=details.get("dependents", 0),
                downloads_weekly=details.get("downloads_weekly", 0),
                documentation_score=doc_score,
                has_examples=bool(re.search(r'example|usage|quickstart', details.get("readme", ""), re.I)),
            ),
            source_url=candidate.url,
            source=candidate.source.value,
            license=candidate.license,
            raw_metadata=candidate.raw_data,
        )

    def score_capabilities(self, resume: Resume, job: JobDescription) -> float:
        """Score capability match for generic OSS using description semantics."""
        # For generic OSS, use keyword matching on description + tool names
        combined = f"{resume.description} {' '.join(t.name for t in resume.tools_provided)}".lower()

        if not job.required_capabilities and not job.preferred_capabilities:
            return 0.5  # neutral score

        # Count how many required capabilities are mentioned
        matches = 0
        for cap in job.required_capabilities:
            if cap.lower() in combined:
                matches += 1

        required_score = matches / max(len(job.required_capabilities), 1)

        # Preferred bonus
        pref_matches = 0
        for cap in job.preferred_capabilities:
            if cap.lower() in combined:
                pref_matches += 1
        pref_bonus = (pref_matches / max(len(job.preferred_capabilities), 1)) * 0.2 if job.preferred_capabilities else 0

        return min(required_score * 0.7 + pref_bonus + 0.1, 1.0)

    @staticmethod
    def _extract_generic_tools(description: str, readme: str) -> list[ToolSignature]:
        """Extract capability-like features from text."""
        import re

        tools: list[ToolSignature] = []
        text = f"{description}\n{readme}"

        # Extract key phrases as "tools"
        patterns = [
            r'(?:feature|capability|support(?:s|ed)?|provides?)\s*[:\-]\s*(.+)',
            r'\*\*([^*]+)\*\*\s*[-–:]\s*(.+)',
            r'##\s*(.+)',
        ]

        found_names: set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name = match.group(1).strip()[:50]
                if name and name.lower() not in {"installation", "usage", "getting started", "license", "contributing"}:
                    if name not in found_names:
                        found_names.add(name)
                        tools.append(ToolSignature(name=name))

        return tools[:15]

    @staticmethod
    def _score_docs(readme: str, description: str) -> float:
        """Heuristic documentation quality score."""
        text = f"{description}\n{readme}"
        score = 0.0
        if len(text) > 1000:
            score += 0.2
        elif len(text) > 300:
            score += 0.1
        if "##" in text:
            score += 0.1
        if "###" in text:
            score += 0.1
        for kw in ["install", "usage", "example", "api"]:
            if kw in text.lower():
                score += 0.15
        return min(score, 1.0)
