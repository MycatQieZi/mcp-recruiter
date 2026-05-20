"""Hard filter — boolean pass/fail conditions for initial screening."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..core.models import HardRequirements, Resume
from ..core.enums import TransportType


@dataclass
class HardFilterResult:
    """Result of applying hard filters to a candidate."""

    passed: bool
    reason: str = ""
    failures: list[str] = field(default_factory=list)


def apply_hard_filters(resume: Resume, requirements: HardRequirements) -> HardFilterResult:
    """Apply all hard filter checks. Returns pass/fail with reason."""
    failures: list[str] = []

    # Check min_stars
    if requirements.min_stars is not None:
        if resume.health.stars < requirements.min_stars:
            failures.append(
                f"Stars ({resume.health.stars}) < required ({requirements.min_stars})"
            )

    # Check max_days_since_update
    if requirements.max_days_since_update is not None:
        if resume.health.last_commit_date:
            days_since = (datetime.now() - resume.health.last_commit_date.replace(tzinfo=None)).days
            if days_since > requirements.max_days_since_update:
                failures.append(
                    f"Last update {days_since} days ago > max {requirements.max_days_since_update}"
                )
        else:
            failures.append("No last update date available")

    # Check min_tool_count
    if requirements.min_tool_count is not None:
        tool_count = len(resume.tools_provided)
        if tool_count < requirements.min_tool_count:
            failures.append(
                f"Tool count ({tool_count}) < required ({requirements.min_tool_count})"
            )

    # Check required_transports (for MCP tools, we infer from raw_metadata)
    if requirements.required_transports:
        supported = _infer_transports(resume)
        missing = set(requirements.required_transports) - supported
        if missing:
            failures.append(
                f"Missing transport(s): {', '.join(t.value for t in missing)}"
            )

    # Check license
    if requirements.require_license:
        if not resume.license:
            failures.append("No license specified")

    if failures:
        return HardFilterResult(
            passed=False,
            reason="; ".join(failures),
            failures=failures,
        )

    return HardFilterResult(passed=True)


def _infer_transports(resume: Resume) -> set[TransportType]:
    """Infer supported transports from resume metadata."""
    transports: set[TransportType] = {TransportType.STDIO}  # default

    # Check raw_metadata for transport hints
    meta = resume.raw_metadata
    description_lower = resume.description.lower()
    readme_lower = ""  # Not available at filter level

    # Keywords indicating transport support
    if "sse" in description_lower or "server-sent events" in description_lower:
        transports.add(TransportType.SSE)

    # Most MCP tools support stdio by default
    # STREAMABLE_HTTP is rare in current ecosystem, require explicit signal
    if "streamable" in description_lower or "streamable http" in description_lower:
        transports.add(TransportType.STREAMABLE_HTTP)

    # Check topics/keywords
    topics = meta.get("topics", [])
    if isinstance(topics, list):
        topic_str = " ".join(topics).lower()
        if "sse" in topic_str:
            transports.add(TransportType.SSE)

    return transports
