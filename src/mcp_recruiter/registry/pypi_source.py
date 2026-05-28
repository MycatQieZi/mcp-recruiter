"""PyPI source — search Python packages for candidate discovery."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from ..core.enums import RegistrySource
from .base import RawCandidate, RegistrySource as AbstractRegistrySource


class PyPISource(AbstractRegistrySource):
    """Search PyPI for Python packages related to MCP, AI agents, and tooling."""

    BASE_URL = "https://pypi.org/pypi"
    SEARCH_URL = "https://pypi.org/search/"

    @property
    def source_type(self) -> RegistrySource:
        return RegistrySource.PYPI

    async def search(self, query: str, limit: int = 20) -> list[RawCandidate]:
        """Search PyPI for packages matching the query."""
        candidates: list[RawCandidate] = []

        # Clean query for PyPI search
        search_terms = query.replace("topic:", "").replace("@", "").strip()
        # Keep only meaningful terms
        words = [w for w in search_terms.split() if len(w) > 1 and w not in {"mcp", "server"}]
        search_query = " ".join(words[:5]) if words else search_terms

        if not search_query.strip():
            search_query = query.strip()

        async with httpx.AsyncClient(timeout=30) as client:
            # Use PyPI's JSON API search
            try:
                params = {"q": search_query}
                resp = await client.get(
                    f"{self.SEARCH_URL}",
                    params=params,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    for item in items[:limit]:
                        candidates.append(self._build_candidate(item))
            except (httpx.HTTPError, ValueError):
                # Fallback: try the simple JSON API
                try:
                    resp = await client.get(
                        f"{self.BASE_URL}/-/search/",
                        params={"q": search_query},
                        headers={"Accept": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", [])[:limit]:
                            candidates.append(self._build_candidate(item))
                except (httpx.HTTPError, ValueError):
                    pass

        return candidates[:limit]

    async def fetch_details(self, candidate: RawCandidate) -> dict[str, Any]:
        """Fetch detailed package metadata from PyPI."""
        details: dict[str, Any] = {
            "readme": "",
            "downloads_weekly": 0,
            "dependents": 0,
            "github_url": "",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch package JSON
                resp = await client.get(f"{self.BASE_URL}/{candidate.identifier}/json")
                if resp.status_code == 200:
                    data = resp.json()
                    info = data.get("info", {})

                    # README (description field in PyPI)
                    details["readme"] = info.get("description", "") or ""

                    # Extract GitHub URL from project_urls
                    urls = info.get("project_urls", {}) or {}
                    for key, url in urls.items():
                        if "github" in url.lower():
                            details["github_url"] = url
                            break

                    # If no GitHub URL in project_urls, check home_page
                    if not details["github_url"]:
                        home = info.get("home_page", "")
                        if "github" in home.lower():
                            details["github_url"] = home

                    # License
                    details["license"] = info.get("license", "")

                    # Downloads (from the last release info)
                    urls_data = data.get("urls", [])
                    total_downloads = sum(u.get("downloads", 0) for u in urls_data)
                    details["downloads_weekly"] = total_downloads

        except httpx.HTTPError:
            pass

        return details

    def _build_candidate(self, item: dict) -> RawCandidate:
        """Build a RawCandidate from a PyPI search result item."""
        name = item.get("name", "")
        version = item.get("version", "")
        description = item.get("summary", "") or item.get("description", "")
        release_date = item.get("release_date", "")

        last_updated = None
        if release_date:
            try:
                last_updated = datetime.fromisoformat(release_date.replace("Z", "+00:00")).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        return RawCandidate(
            source=RegistrySource.PYPI,
            identifier=name,
            name=f"{name} v{version}" if version else name,
            description=description[:500],
            url=f"https://pypi.org/project/{name}/",
            language="Python",
            topics=self._extract_keywords(item),
            last_updated=last_updated,
            raw_data=item,
        )

    @staticmethod
    def _extract_keywords(item: dict) -> list[str]:
        """Extract keywords/topics from PyPI package metadata."""
        keywords = item.get("keywords", "")
        if isinstance(keywords, str) and keywords:
            return [k.strip() for k in keywords.split(",") if k.strip()]
        if isinstance(keywords, list):
            return keywords
        return []

    def rate_limit_info(self) -> dict[str, Any]:
        return {"note": "PyPI has no strict rate limits for reasonable use"}
