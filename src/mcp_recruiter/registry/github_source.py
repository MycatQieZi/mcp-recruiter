"""GitHub registry source — search for MCP servers via GitHub API."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import httpx

from ..core.enums import RegistrySource
from .base import RawCandidate, RegistrySource as AbstractRegistrySource


class GitHubSource(AbstractRegistrySource):
    """Search GitHub repositories for MCP server implementations."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str = ""):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self._last_request_time = 0.0
        self._min_interval = 0.1  # rate limiting safety

    @property
    def source_type(self) -> RegistrySource:
        return RegistrySource.GITHUB

    def _headers(self) -> dict:
        h = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _rate_limit_wait(self):
        """Simple client-side rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    async def search(self, query: str, limit: int = 20) -> list[RawCandidate]:
        """Search GitHub for MCP server repos using multi-strategy.

        Uses GitHub's repository search API with topic filtering.
        """
        candidates: list[RawCandidate] = []

        async with httpx.AsyncClient(timeout=30) as client:
            candidates = await self._search_repos(client, query, limit)

        return candidates[:limit]

    async def search_code(self, query: str, limit: int = 10) -> list[RawCandidate]:
        """Search GitHub code for files containing MCP-related imports.

        This finds repos that actually implement MCP but may not have
        the 'mcp' or 'mcp-server' topic tags.
        """
        candidates: list[RawCandidate] = []
        seen_repos: set[str] = set()

        async with httpx.AsyncClient(timeout=30) as client:
            # Search for MCP SDK import patterns in code
            code_queries = [
                f'"@modelcontextprotocol/sdk" {query}',
                f'"from mcp" {query}',
                f'"import mcp" {query}',
                f'"mcp.server" {query}',
            ]

            for code_query in code_queries[:2]:  # Limit to avoid rate issues
                params = {
                    "q": code_query,
                    "per_page": min(limit, 10),
                }
                self._rate_limit_wait()
                resp = await client.get(
                    f"{self.BASE_URL}/search/code",
                    headers=self._headers(),
                    params=params,
                )
                self._last_request_time = time.time()

                if resp.status_code != 200:
                    continue

                data = resp.json()
                for item in data.get("items", []):
                    repo_info = item.get("repository", {})
                    full_name = repo_info.get("full_name", "")
                    if full_name in seen_repos:
                        continue
                    seen_repos.add(full_name)

                    candidates.append(RawCandidate(
                        source=RegistrySource.GITHUB,
                        identifier=full_name,
                        name=repo_info.get("name", ""),
                        description=repo_info.get("description", "") or "",
                        url=repo_info.get("html_url", ""),
                        stars=repo_info.get("stargazers_count", 0),
                        language=repo_info.get("language", ""),
                        topics=repo_info.get("topics", []),
                        last_updated=self._parse_date(repo_info.get("pushed_at")),
                        open_issues=repo_info.get("open_issues_count", 0),
                        license=(repo_info.get("license") or {}).get("spdx_id", ""),
                        raw_data=repo_info,
                    ))

        return candidates[:limit]

    async def search_by_readme(self, query: str, limit: int = 10) -> list[RawCandidate]:
        """Search GitHub repos by README content to find relevant projects."""
        candidates: list[RawCandidate] = []
        seen_repos: set[str] = set()

        async with httpx.AsyncClient(timeout=30) as client:
            readme_query = f"{query} in:readme"
            params = {
                "q": readme_query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(limit, 10),
            }
            self._rate_limit_wait()
            resp = await client.get(
                f"{self.BASE_URL}/search/repositories",
                headers=self._headers(),
                params=params,
            )
            self._last_request_time = time.time()

            if resp.status_code != 200:
                return candidates

            data = resp.json()
            for item in data.get("items", []):
                full_name = item.get("full_name", "")
                if full_name in seen_repos:
                    continue
                seen_repos.add(full_name)

                candidates.append(RawCandidate(
                    source=RegistrySource.GITHUB,
                    identifier=full_name,
                    name=item.get("name", ""),
                    description=item.get("description", "") or "",
                    url=item.get("html_url", ""),
                    stars=item.get("stargazers_count", 0),
                    language=item.get("language", ""),
                    topics=item.get("topics", []),
                    last_updated=self._parse_date(item.get("pushed_at")),
                    open_issues=item.get("open_issues_count", 0),
                    license=(item.get("license") or {}).get("spdx_id", ""),
                    raw_data=item,
                ))

        return candidates[:limit]

    async def search_all_strategies(self, query: str, limit_per: int = 10) -> list[RawCandidate]:
        """Run all search strategies and return merged, deduplicated results."""
        topic_results = await self.search(query, limit=limit_per)
        code_results = await self.search_code(query, limit=limit_per)
        readme_results = await self.search_by_readme(query, limit=limit_per)

        seen: set[str] = set()
        merged: list[RawCandidate] = []
        for c in topic_results + code_results + readme_results:
            if c.identifier not in seen:
                seen.add(c.identifier)
                merged.append(c)

        return sorted(merged, key=lambda x: x.stars, reverse=True)

    async def _search_repos(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> list[RawCandidate]:
        """Internal: search repos by topic query."""
        # Build search query: MCP topic + user query terms
        search_query = f"topic:mcp topic:mcp-server {query}"
        candidates: list[RawCandidate] = []

        page = 1
        while len(candidates) < limit and page <= 3:
            params = {
                "q": search_query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(limit, 30),
                "page": page,
            }
            self._rate_limit_wait()
            resp = await client.get(
                f"{self.BASE_URL}/search/repositories",
                headers=self._headers(),
                params=params,
            )
            self._last_request_time = time.time()

            if resp.status_code != 200:
                break

            data = resp.json()
            items = data.get("items", [])

            for item in items:
                c = RawCandidate(
                    source=RegistrySource.GITHUB,
                    identifier=item.get("full_name", ""),
                    name=item.get("name", ""),
                    description=item.get("description", "") or "",
                    url=item.get("html_url", ""),
                    stars=item.get("stargazers_count", 0),
                    language=item.get("language", ""),
                    topics=item.get("topics", []),
                    last_updated=self._parse_date(item.get("pushed_at")),
                    open_issues=item.get("open_issues_count", 0),
                    license=(item.get("license") or {}).get("spdx_id", ""),
                    raw_data=item,
                )
                candidates.append(c)

            if len(items) < params["per_page"]:
                break
            page += 1

        return candidates[:limit]

    async def fetch_details(self, candidate: RawCandidate) -> dict[str, Any]:
        """Fetch README and additional metadata for a candidate."""
        details: dict[str, Any] = {"readme": "", "contributors_count": 0}

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch README
            self._rate_limit_wait()
            resp = await client.get(
                f"{self.BASE_URL}/repos/{candidate.identifier}/readme",
                headers=self._headers(),
            )
            self._last_request_time = time.time()
            if resp.status_code == 200:
                readme_data = resp.json()
                readme_content = readme_data.get("content", "")
                import base64
                try:
                    details["readme"] = base64.b64decode(readme_content).decode("utf-8", errors="replace")
                except Exception:
                    details["readme"] = ""

            # Fetch contributors count (just use the list endpoint for count approximation)
            # For efficiency, just check the contributor count header
            self._rate_limit_wait()
            resp = await client.get(
                f"{self.BASE_URL}/repos/{candidate.identifier}/contributors",
                headers=self._headers(),
                params={"per_page": 1, "anon": "true"},
            )
            self._last_request_time = time.time()
            if resp.status_code == 200:
                # Use the Link header to estimate count
                link_header = resp.headers.get("Link", "")
                if "last" in link_header:
                    try:
                        # Parse GitHub's pagination Link header
                        last_part = link_header.split("rel=\"last\"")[0].split("<")[-1].rstrip(">; ")
                        if "page=" in last_part:
                            details["contributors_count"] = int(last_part.split("page=")[-1])
                    except (ValueError, IndexError):
                        details["contributors_count"] = len(resp.json())

        return details

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return None
