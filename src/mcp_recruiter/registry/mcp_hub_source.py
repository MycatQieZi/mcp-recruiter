"""MCP Hub source — search community-curated MCP server listings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from ..core.enums import RegistrySource
from .base import RawCandidate, RegistrySource as AbstractRegistrySource


class MCPHubSource(AbstractRegistrySource):
    """Search community MCP hub/server listing sites.

    Attempts to fetch from known community indices.
    Falls back to an embedded static list if network is unavailable.
    """

    HUB_URLS = [
        "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md",
    ]

    @property
    def source_type(self) -> RegistrySource:
        return RegistrySource.MCP_HUB

    async def search(self, query: str, limit: int = 20) -> list[RawCandidate]:
        """Search MCP Hub listings for matching servers."""
        candidates: list[RawCandidate] = []

        # Try fetching from community indices
        async with httpx.AsyncClient(timeout=30) as client:
            for url in self.HUB_URLS:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        extracted = self._parse_readme_links(resp.text)
                        candidates.extend(extracted)
                except httpx.HTTPError:
                    continue

        # Fallback: embedded known MCP servers list
        if not candidates:
            candidates = self._static_fallback()

        # Filter by query (simple substring match on name + description)
        query_lower = query.lower().strip()
        if query_lower:
            filtered = []
            for c in candidates:
                if (
                    query_lower in c.name.lower()
                    or query_lower in c.description.lower()
                    or any(query_lower in t.lower() for t in c.topics)
                ):
                    filtered.append(c)
            candidates = filtered
        else:
            # If no query, return all
            pass

        return candidates[:limit]

    async def fetch_details(self, candidate: RawCandidate) -> dict[str, Any]:
        """Return raw_data as the details (MCP Hub entries are already detailed enough)."""
        return {"readme": candidate.description, **candidate.raw_data}

    def _parse_readme_links(self, readme_text: str) -> list[RawCandidate]:
        """Extract MCP server entries from a markdown list of links."""
        import re

        candidates: list[RawCandidate] = []
        # Pattern: [name](url) — description
        pattern = r'\[([^\]]+)\]\(([^)]+)\)(?:\s*[-–—]\s*(.+))?'
        for match in re.finditer(pattern, readme_text):
            name = match.group(1).strip()
            url = match.group(2).strip()
            desc = (match.group(3) or "").strip()

            if not name or not url:
                continue

            # Skip non-MCP related links
            candidates.append(
                RawCandidate(
                    source=RegistrySource.MCP_HUB,
                    identifier=name,
                    name=name,
                    description=desc,
                    url=url,
                )
            )

        return candidates

    def _static_fallback(self) -> list[RawCandidate]:
        """Embedded known MCP servers list as a fallback when network is unavailable."""
        known_servers = [
            ("@modelcontextprotocol/server-filesystem", "Filesystem access MCP server"),
            ("@modelcontextprotocol/server-github", "GitHub API MCP server"),
            ("@modelcontextprotocol/server-postgres", "PostgreSQL MCP server"),
            ("@modelcontextprotocol/server-sqlite", "SQLite MCP server"),
            ("@modelcontextprotocol/server-brave-search", "Brave Search MCP server"),
            ("@modelcontextprotocol/server-puppeteer", "Puppeteer browser automation MCP server"),
            ("@modelcontextprotocol/server-memory", "Knowledge graph memory MCP server"),
            ("@modelcontextprotocol/server-fetch", "Web fetching MCP server"),
            ("@modelcontextprotocol/server-everything", "Reference/test MCP server"),
            ("@anthropic/mcp-server-gsuite", "Google Suite MCP server"),
        ]
        return [
            RawCandidate(
                source=RegistrySource.MCP_HUB,
                identifier=name,
                name=name,
                description=desc,
                url=f"https://www.npmjs.com/package/{name}" if name.startswith("@") else "",
            )
            for name, desc in known_servers
        ]
