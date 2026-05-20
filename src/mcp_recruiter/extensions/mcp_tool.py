"""MCP Tool handler — implementation for MCP Tool candidate type."""

from __future__ import annotations

from ..core.enums import CandidateType
from ..core.models import JobDescription, Resume
from ..registry.base import RawCandidate
from ..screening.resume_builder import build_resume as build_mcp_resume
from ..screening.soft_scorer import score_capability as mcp_score_capability
from .base import CandidateTypeHandler


class MCPToolHandler(CandidateTypeHandler):
    """Handler for MCP Tool candidates."""

    @property
    def candidate_type(self) -> CandidateType:
        return CandidateType.MCP_TOOL

    def detect(self, raw_metadata: dict) -> bool:
        return raw_metadata.get("type") in ("mcp_tool", "mcp")

    def build_resume(self, raw_metadata: dict) -> Resume:
        # Convert dict back to RawCandidate, then build resume
        from ..registry.base import RawCandidate

        candidate = RawCandidate(
            source=raw_metadata.get("source", "unknown"),
            identifier=raw_metadata.get("identifier", ""),
            name=raw_metadata.get("name", ""),
            description=raw_metadata.get("description", ""),
            url=raw_metadata.get("url", ""),
            stars=raw_metadata.get("stars", 0),
            raw_data=raw_metadata,
        )
        return build_mcp_resume(candidate)

    def score_capabilities(self, resume: Resume, job: JobDescription) -> float:
        return mcp_score_capability(resume, job)
