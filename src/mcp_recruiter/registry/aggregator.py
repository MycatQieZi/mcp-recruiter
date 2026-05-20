"""Multi-source registry aggregator with deduplication and caching."""

from __future__ import annotations

import asyncio
from typing import Any

from ..core.enums import RegistrySource as RS
from .base import RawCandidate, RegistrySource
from .cache import RegistryCache
from .github_source import GitHubSource
from .mcp_hub_source import MCPHubSource
from .npm_source import NpmSource


class RegistryAggregator:
    """Orchestrates search across multiple registry sources."""

    def __init__(self, cache_dir: str = "./data/cache", github_token: str = ""):
        self.sources: dict[RS, RegistrySource] = {
            RS.GITHUB: GitHubSource(token=github_token),
            RS.NPM: NpmSource(),
            RS.MCP_HUB: MCPHubSource(),
        }
        self.cache = RegistryCache(cache_dir)

    async def search(self, query: str, limit_per_source: int = 15) -> list[RawCandidate]:
        """Search all sources, deduplicate, and return merged results."""
        all_candidates: list[RawCandidate] = []

        # Check cache first
        for source_type, source in self.sources.items():
            cache_key = source_type.value
            cached = self.cache.get(cache_key, query)
            if cached:
                all_candidates.extend([self._deserialize_candidate(c, source_type) for c in cached])
                continue

            try:
                results = await source.search(query, limit=limit_per_source)
                # Cache results
                serialized = [self._serialize_candidate(r) for r in results]
                ttl = self._ttl_for_source(source_type)
                self.cache.set(cache_key, query, serialized, ttl)
                all_candidates.extend(results)
            except Exception as e:
                # Log but continue with other sources
                print(f"[warn] Source {source_type.value} failed: {e}")

        # Deduplicate
        deduped = self._deduplicate(all_candidates)
        return deduped

    def _deduplicate(self, candidates: list[RawCandidate]) -> list[RawCandidate]:
        """Deduplicate by preferring GitHub > npm > MCP_Hub."""
        seen: dict[str, RawCandidate] = {}
        priority = {RS.GITHUB: 3, RS.NPM: 2, RS.MCP_HUB: 1}

        for c in candidates:
            key = self._canonical_key(c)
            if key in seen:
                existing_priority = priority.get(seen[key].source, 0)
                new_priority = priority.get(c.source, 0)
                if new_priority > existing_priority:
                    seen[key] = c
            else:
                seen[key] = c

        # Sort by stars descending
        return sorted(seen.values(), key=lambda x: x.stars, reverse=True)

    @staticmethod
    def _canonical_key(c: RawCandidate) -> str:
        """Generate a canonical deduplication key."""
        # Normalize: lowercase, strip @ prefix for npm packages
        name = c.name.lower().strip()
        if name.startswith("@"):
            parts = name.split("/", 1)
            name = parts[-1] if len(parts) > 1 else name
        # Remove 'mcp-server-' prefix for fuzzy matching
        for prefix in ["mcp-server-", "mcp-", "server-"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name

    @staticmethod
    def _ttl_for_source(source_type: RS) -> int:
        return {RS.GITHUB: 3600, RS.NPM: 21600, RS.MCP_HUB: 86400}[source_type]

    @staticmethod
    def _serialize_candidate(c: RawCandidate) -> dict[str, Any]:
        return {
            "source": c.source.value,
            "identifier": c.identifier,
            "name": c.name,
            "description": c.description,
            "url": c.url,
            "stars": c.stars,
            "language": c.language,
            "topics": c.topics,
            "last_updated": c.last_updated.isoformat() if c.last_updated else None,
            "open_issues": c.open_issues,
            "license": c.license,
            "raw_data": c.raw_data,
        }

    @staticmethod
    def _deserialize_candidate(data: dict, source_type: RS) -> RawCandidate:
        from datetime import datetime

        lu = data.get("last_updated")
        if lu:
            lu = datetime.fromisoformat(lu)

        return RawCandidate(
            source=source_type,
            identifier=data.get("identifier", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            url=data.get("url", ""),
            stars=data.get("stars", 0),
            language=data.get("language", ""),
            topics=data.get("topics", []),
            last_updated=lu,
            open_issues=data.get("open_issues", 0),
            license=data.get("license", ""),
            raw_data=data.get("raw_data", {}),
        )
