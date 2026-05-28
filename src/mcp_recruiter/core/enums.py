from __future__ import annotations

from enum import Enum


class Stage(str, Enum):
    """Pipeline stages matching the hiring metaphor."""

    SEA = "sea"  # 海选: market scan
    SCREEN = "screen"  # 初试: initial screening
    WRITTEN = "written"  # 笔试: sandbox testing
    INTERVIEW = "interview"  # 终面: final report
    COMPLETE = "complete"


class CandidateType(str, Enum):
    """Types of technical solutions that can be evaluated."""

    MCP_TOOL = "mcp_tool"
    API = "api"  # future
    AGENT = "agent"  # future
    SKILL = "skill"  # future


class TransportType(str, Enum):
    """MCP transport types."""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class RegistrySource(str, Enum):
    """Data sources for candidate discovery."""

    GITHUB = "github"
    NPM = "npm"
    MCP_HUB = "mcp_hub"
    AWESOME = "awesome"
    WEB_SEARCH = "web_search"
    PYPI = "pypi"


class ExpectedBehavior(str, Enum):
    """How to validate test case outputs."""

    EXACT_MATCH = "exact_match"
    CONTAINS = "contains"
    SCHEMA_MATCH = "schema_match"
    NO_ERROR = "no_error"


class ScoringPreset(str, Enum):
    """Pre-configured scoring weight profiles."""

    BALANCED = "balanced"
    PERF_FIRST = "perf_first"
    COMMUNITY_FIRST = "community_first"
    QUICK_SCAN = "quick_scan"
