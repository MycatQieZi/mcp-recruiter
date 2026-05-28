"""Awesome list source — parse community-curated awesome lists for candidates."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx

from ..core.enums import RegistrySource
from .base import RawCandidate, RegistrySource as AbstractRegistrySource


class AwesomeListSource(AbstractRegistrySource):
    """Parse curated 'awesome-*' lists from GitHub for candidate discovery.

    Scans repositories like awesome-mcp-servers, awesome-mcp-clients,
    awesome-ai-agents, etc. to find community-recommended projects.
    """

    # Curated list of awesome-list README URLs
    DEFAULT_LISTS = [
        "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md",
        "https://raw.githubusercontent.com/punkpeye/awesome-mcp-clients/main/README.md",
        "https://raw.githubusercontent.com/wshobson/awesome-mcp-agents/main/README.md",
        "https://raw.githubusercontent.com/e2b-dev/awesome-ai-agents/main/README.md",
        "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md",
    ]

    @property
    def source_type(self) -> RegistrySource:
        return RegistrySource.AWESOME

    async def search(self, query: str, limit: int = 30) -> list[RawCandidate]:
        """Search awesome lists for matching candidates."""
        all_candidates: list[RawCandidate] = []

        async with httpx.AsyncClient(timeout=60) as client:
            for list_url in self.DEFAULT_LISTS:
                try:
                    resp = await client.get(list_url)
                    if resp.status_code == 200:
                        extracted = self._parse_markdown_list(resp.text, list_url)
                        all_candidates.extend(extracted)
                except httpx.HTTPError:
                    continue

        # Filter by query
        if query and query.strip():
            query_lower = query.lower().strip()
            filtered = []
            for c in all_candidates:
                if (
                    query_lower in c.name.lower()
                    or query_lower in c.description.lower()
                    or any(query_lower in t.lower() for t in c.topics)
                ):
                    filtered.append(c)
            all_candidates = filtered

        # For GitHub repos found in awesome lists, try to enrich with star counts
        await self._enrich_github_stars(all_candidates[:30])

        return all_candidates[:limit]

    async def fetch_details(self, candidate: RawCandidate) -> dict[str, Any]:
        """Fetch README from the candidate's GitHub URL if available."""
        details: dict[str, Any] = {"readme": candidate.description, "contributors_count": 0}

        if "github.com" in candidate.url:
            # Extract owner/repo from URL
            match = re.search(r'github\.com/([^/]+/[^/\s#]+)', candidate.url)
            if match:
                repo = match.group(1).rstrip('/')
                async with httpx.AsyncClient(timeout=30) as client:
                    try:
                        resp = await client.get(
                            f"https://api.github.com/repos/{repo}/readme",
                            headers={"Accept": "application/vnd.github.v3+json"},
                        )
                        if resp.status_code == 200:
                            import base64
                            data = resp.json()
                            content = data.get("content", "")
                            try:
                                details["readme"] = base64.b64decode(content).decode("utf-8", errors="replace")
                            except Exception:
                                pass
                    except httpx.HTTPError:
                        pass

        return details

    def _parse_markdown_list(self, md_text: str, source_url: str) -> list[RawCandidate]:
        """Extract candidate entries from an awesome-list markdown file."""
        candidates: list[RawCandidate] = []

        # Pattern: [name](url) — description or • [name](url) - description
        patterns = [
            # Standard markdown link with dash/em-dash description
            r'(?:^|\n)\s*(?:[-*•]\s*)?\[([^\]]+)\]\(([^)]+)\)\s*[-–—]\s*(.+?)(?=\n|$)',
            # Parenthesized description: [name](url) (description)
            r'(?:^|\n)\s*(?:[-*•]\s*)?\[([^\]]+)\]\(([^)]+)\)\s*\((.+?)\)(?=\n|$)',
            # Simple link without description
            r'(?:^|\n)\s*(?:[-*•]\s*)?\[([^\]]+)\]\(([^)]+)\)(?:\s*$|\n)',
            # Nested list items (indented)
            r'(?:^|\n)\s{2,}(?:[-*•]\s*)?\[([^\]]+)\]\(([^)]+)\)\s*[-–—]\s*(.+?)(?=\n|$)',
        ]

        seen_identifiers: set[str] = set()

        for pattern in patterns:
            for match in re.finditer(pattern, md_text, re.MULTILINE):
                groups = match.groups()
                name = groups[0].strip()
                url = groups[1].strip()
                desc = groups[2].strip() if len(groups) > 2 else ""

                if not name or not url:
                    continue

                # Skip section headers, TOC entries, and non-project links
                skip_patterns = [
                    r'^#', r'^table of contents', r'^contribut', r'^license',
                    r'^awesome', r'^contents$', r'^- ', r'^\* ',
                ]
                if any(re.match(p, name.lower()) for p in skip_patterns):
                    continue

                identifier = url
                if identifier in seen_identifiers:
                    continue
                seen_identifiers.add(identifier)

                # Extract topics from name and description context
                topics = self._extract_topics(name, desc)

                candidates.append(RawCandidate(
                    source=RegistrySource.AWESOME,
                    identifier=identifier,
                    name=name,
                    description=desc[:500],
                    url=url,
                    topics=topics,
                ))

        return candidates

    async def _enrich_github_stars(self, candidates: list[RawCandidate]):
        """Fetch star counts for GitHub repos found in awesome lists."""
        github_repos = [c for c in candidates if "github.com" in c.url]

        if not github_repos:
            return

        async with httpx.AsyncClient(timeout=30) as client:
            for c in github_repos:
                match = re.search(r'github\.com/([^/]+/[^/\s#]+)', c.url)
                if not match:
                    continue
                repo = match.group(1).rstrip('/')
                try:
                    resp = await client.get(
                        f"https://api.github.com/repos/{repo}",
                        headers={"Accept": "application/vnd.github.v3+json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        c.stars = data.get("stargazers_count", 0)
                        c.language = data.get("language", "")
                        c.topics = data.get("topics", c.topics)
                        c.open_issues = data.get("open_issues_count", 0)
                        c.license = (data.get("license") or {}).get("spdx_id", "")
                        pushed = data.get("pushed_at")
                        if pushed:
                            try:
                                c.last_updated = datetime.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ")
                            except ValueError:
                                pass
                        c.raw_data = data
                except httpx.HTTPError:
                    continue

    @staticmethod
    def _extract_topics(name: str, description: str) -> list[str]:
        """Extract topic-like keywords from name and description."""
        topics: list[str] = []
        combined = f"{name} {description}".lower()

        keyword_map = {
            "mcp": "mcp",
            "server": "mcp-server",
            "client": "mcp-client",
            "agent": "ai-agent",
            "ai": "ai",
            "llm": "llm",
            "tool": "tool",
            "api": "api",
            "database": "database",
            "file": "filesystem",
            "search": "search",
            "browser": "browser",
            "memory": "memory",
            "http": "http",
        }
        for keyword, topic in keyword_map.items():
            if keyword in combined:
                topics.append(topic)

        return list(dict.fromkeys(topics))  # deduplicate, preserve order
