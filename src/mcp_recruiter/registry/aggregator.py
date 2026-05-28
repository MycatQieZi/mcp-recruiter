"""Multi-source registry aggregator with deduplication and caching."""

from __future__ import annotations

import asyncio
from typing import Any

from ..core.enums import RegistrySource as RS
from ..core.llm_client import SearchQueryVariant
from .base import RawCandidate, RegistrySource
from .cache import RegistryCache
from .github_source import GitHubSource
from .mcp_hub_source import MCPHubSource
from .npm_source import NpmSource
from .web_search_source import WebSearchSource
from .awesome_list_source import AwesomeListSource
from .pypi_source import PyPISource


class RegistryAggregator:
    """Orchestrates search across multiple registry sources."""

    def __init__(
        self,
        cache_dir: str = "./data/cache",
        github_token: str = "",
        enable_web: bool = True,
        enable_awesome: bool = True,
        enable_pypi: bool = True,
    ):
        self.sources: dict[RS, RegistrySource] = {
            RS.GITHUB: GitHubSource(token=github_token),
            RS.NPM: NpmSource(),
            RS.MCP_HUB: MCPHubSource(),
        }
        if enable_web:
            self.sources[RS.WEB_SEARCH] = WebSearchSource()
        if enable_awesome:
            self.sources[RS.AWESOME] = AwesomeListSource()
        if enable_pypi:
            self.sources[RS.PYPI] = PyPISource()

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
        """Deduplicate by preferring GitHub > npm > MCP_Hub > PyPI > Awesome > Web."""
        seen: dict[str, RawCandidate] = {}
        priority = {
            RS.GITHUB: 6, RS.NPM: 5, RS.MCP_HUB: 4,
            RS.PYPI: 3, RS.AWESOME: 2, RS.WEB_SEARCH: 1,
        }

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

    async def search_with_variants(
        self,
        variants: list[SearchQueryVariant],
        limit_per_source: int = 15,
    ) -> list[RawCandidate]:
        """Search all sources with multiple query variants and merge results.

        Each SearchQueryVariant targets a specific source type with a specific query.
        Results from all variants are deduplicated and ranked by stars.
        """
        all_candidates: list[RawCandidate] = []
        tasks: list[asyncio.Task] = []

        async def _search_source(
            source_type: RS, source: RegistrySource, query: str
        ) -> list[RawCandidate]:
            try:
                return await source.search(query, limit=limit_per_source)
            except Exception as e:
                print(f"[warn] Source {source_type.value} query '{query[:40]}...' failed: {e}")
                return []

        # Group variants by source type and create tasks
        for variant in variants:
            source_type = RS.GITHUB  # default
            if variant.source_type == "github_topic":
                source_type = RS.GITHUB
            elif variant.source_type == "github_code":
                source_type = RS.GITHUB
            elif variant.source_type == "github_readme":
                source_type = RS.GITHUB
            elif variant.source_type == "web":
                source_type = RS.WEB_SEARCH
            elif variant.source_type == "pypi":
                source_type = RS.PYPI
            elif variant.source_type == "awesome":
                source_type = RS.AWESOME

            source = self.sources.get(source_type)
            if source is None:
                continue

            tasks.append(_search_source(source_type, source, variant.query_string))

        # Also add the default NPM and MCP_HUB searches using first variant's keywords
        for source_type, source in self.sources.items():
            if source_type in (RS.NPM, RS.MCP_HUB):
                for variant in variants[:2]:  # Use first 2 variants
                    tasks.append(_search_source(source_type, source, variant.query_string))

        # Run all tasks concurrently
        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                all_candidates.extend(result)

        # Deduplicate across all sources
        deduped = self._deduplicate(all_candidates)
        return deduped

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
