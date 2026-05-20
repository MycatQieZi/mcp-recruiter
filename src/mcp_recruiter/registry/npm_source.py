"""npm registry source — search for MCP server packages."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from ..core.enums import RegistrySource
from .base import RawCandidate, RegistrySource as AbstractRegistrySource


class NpmSource(AbstractRegistrySource):
    """Search npm registry for MCP server packages."""

    BASE_URL = "https://registry.npmjs.org"
    SEARCH_URL = "https://registry.npmjs.org/-/v1/search"

    @property
    def source_type(self) -> RegistrySource:
        return RegistrySource.NPM

    async def search(self, query: str, limit: int = 20) -> list[RawCandidate]:
        """Search npm for packages tagged with MCP-related keywords."""
        candidates: list[RawCandidate] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Search for MCP server packages
            search_text = f"keywords:@modelcontextprotocol/server {query}"
            params = {
                "text": search_text,
                "size": min(limit, 250),
            }
            resp = await client.get(self.SEARCH_URL, params=params)

            if resp.status_code != 200:
                return candidates

            data = resp.json()
            objects = data.get("objects", [])

            for obj in objects:
                pkg = obj.get("package", {})
                c = RawCandidate(
                    source=RegistrySource.NPM,
                    identifier=pkg.get("name", ""),
                    name=pkg.get("name", ""),
                    description=pkg.get("description", "") or "",
                    url=pkg.get("links", {}).get("npm", ""),
                    stars=0,  # npm doesn't have stars
                    language="TypeScript",  # most MCP servers are TS/JS
                    topics=pkg.get("keywords", []),
                    last_updated=self._parse_date(pkg.get("date")),
                    raw_data=pkg,
                )
                candidates.append(c)

        return candidates[:limit]

    async def fetch_details(self, candidate: RawCandidate) -> dict[str, Any]:
        """Fetch detailed package metadata."""
        details: dict[str, Any] = {
            "readme": "",
            "downloads_weekly": 0,
            "dependents": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch package info
                resp = await client.get(f"{self.BASE_URL}/{candidate.identifier}")
                if resp.status_code == 200:
                    data = resp.json()
                    details["readme"] = data.get("readme", "")

                # Fetch download counts
                # Use the abbreviated API to get just download count
                resp = await client.get(
                    f"{self.BASE_URL}/-/v1/downloads/point/last-week/{candidate.identifier}"
                )
                if resp.status_code == 200:
                    dl_data = resp.json()
                    details["downloads_weekly"] = dl_data.get("downloads", 0)

        except httpx.HTTPError:
            pass

        return details

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            return None
