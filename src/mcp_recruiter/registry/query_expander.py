"""Search query expander — orchestrates LLM-based query expansion for multi-source search."""

from __future__ import annotations

from ..core.llm_client import LLMClient, SearchQueryVariant
from ..core.models import JobDescription


class QueryExpander:
    """Expands a JobDescription into multiple search query variants across sources."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def expand(self, job: JobDescription) -> list[SearchQueryVariant]:
        """Generate diverse search queries from a JobDescription."""
        if not self.llm.available:
            return self.llm._fallback_queries(job.title, job.required_capabilities)

        return await self.llm.expand_search_queries(
            title=job.title,
            problem_statement=job.problem_statement,
            required_capabilities=job.required_capabilities,
            preferred_capabilities=job.preferred_capabilities,
        )
