"""Resume builder — generates standardized Resume from RawCandidate data."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import uuid4

from ..core.enums import CandidateType, TransportType
from ..core.models import (
    EcosystemMetrics,
    HealthMetrics,
    Resume,
    ToolSignature,
)
from ..registry.base import RawCandidate


def build_resume(candidate: RawCandidate, details: dict | None = None) -> Resume:
    """Build a standardized Resume from a raw candidate and optional details."""
    details = details or {}

    # Parse README for tool signatures
    tools = _extract_tools(candidate.description, details.get("readme", ""))

    # Parse resources from description
    resources = _extract_resources(candidate.description, details.get("readme", ""))

    # One-line pitch: extract first meaningful sentence
    pitch = _extract_pitch(candidate.description)

    resume = Resume(
        id=uuid4(),
        candidate_id=uuid4(),
        display_name=candidate.name,
        one_line_pitch=pitch,
        description=candidate.description,
        candidate_type=CandidateType.MCP_TOOL,
        tools_provided=tools,
        resources=resources,
        health=HealthMetrics(
            stars=candidate.stars,
            open_issues=candidate.open_issues,
            last_commit_date=candidate.last_updated,
            contributor_count=details.get("contributors_count", 0),
        ),
        ecosystem=EcosystemMetrics(
            dependents=details.get("dependents", 0),
            downloads_weekly=details.get("downloads_weekly", 0),
            documentation_score=_score_docs(details.get("readme", ""), candidate.description),
            has_examples=bool(re.search(r'example|usage|quickstart', details.get("readme", ""), re.I)),
        ),
        source_url=candidate.url,
        source=candidate.source.value,
        license=candidate.license,
        raw_metadata=candidate.raw_data,
    )
    return resume


def _extract_tools(description: str, readme: str) -> list[ToolSignature]:
    """Extract tool signatures from description and README."""
    tools: list[ToolSignature] = []
    text = f"{description}\n{readme}"

    # Pattern 1: look for tool name patterns in the text
    # Common patterns in MCP server READMEs
    tool_patterns = [
        r'(?:###|##)\s*(?:Tools?|Resources?|Capabilities?)',
        r'["\'](\w+(?:_\w+)*)["\']\s*[:=]\s*\{',  # JSON-like tool definitions
        r'\*\*(\w+(?:_\w+)*)\*\*\s*[-–:]\s*(.+)',  # Bold tool names with descriptions
    ]

    found_names: set[str] = set()

    for pattern in tool_patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            if len(match.groups()) >= 1:
                name = match.group(1).strip()
                desc = match.group(2).strip() if len(match.groups()) >= 2 else ""
                if name and name.lower() not in {"tools", "resources", "tool", "resource", "introduction", "overview"}:
                    if name not in found_names:
                        found_names.add(name)
                        tools.append(ToolSignature(name=name, description=desc))

    # If no structured tools found, try extracting from function/capability mentions
    if not tools and description:
        # Extract noun phrases that look like tools (capitalized or code-formatted)
        desc_tools = re.findall(r'`(\w+)`', description)
        for t in desc_tools[:5]:
            if t not in found_names and len(t) > 2:
                found_names.add(t)
                tools.append(ToolSignature(name=t))

    return tools[:20]  # cap at 20


def _extract_resources(description: str, readme: str) -> list[str]:
    """Extract resource names from description and README."""
    text = f"{description}\n{readme}"
    resources: list[str] = []

    # Look for resource patterns
    for match in re.finditer(r'(?:resource[s]?|uri)[s]?\s*[:=]\s*["\']([^"\']+)["\']', text, re.I):
        resources.append(match.group(1))

    return list(dict.fromkeys(resources))  # deduplicate while preserving order


def _extract_pitch(description: str) -> str:
    """Extract the first meaningful sentence as a one-line pitch."""
    if not description:
        return ""

    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', description.strip())
    if sentences:
        first = sentences[0].strip()
        # Limit to ~120 chars
        if len(first) > 120:
            first = first[:117] + "..."
        return first
    return description[:120]


def _score_docs(readme: str, description: str) -> float:
    """Heuristic documentation quality score (0-1)."""
    score = 0.0
    text = f"{description}\n{readme}"

    # Length
    if len(text) > 1000:
        score += 0.2
    elif len(text) > 300:
        score += 0.1

    # Structure indicators
    if "##" in text:
        score += 0.1
    if "###" in text:
        score += 0.1

    # Quality indicators
    has_install = any(kw in text.lower() for kw in ["install", "npm install", "pip install", "npx"])
    has_config = any(kw in text.lower() for kw in ["configuration", "config", "setup", "environment variables"])
    has_usage = any(kw in text.lower() for kw in ["usage", "example", "quickstart", "getting started"])
    has_api = any(kw in text.lower() for kw in ["api", "endpoint", "tool"])

    if has_install:
        score += 0.15
    if has_config:
        score += 0.15
    if has_usage:
        score += 0.15
    if has_api:
        score += 0.15

    return min(score, 1.0)
