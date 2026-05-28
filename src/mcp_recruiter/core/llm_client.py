"""LLM client — OpenAI API wrapper for JD generation and search query expansion."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class SearchQueryVariant:
    """A single search query variant targeting a specific source."""

    query_string: str
    source_type: str  # "github_topic", "github_code", "github_readme", "web", "pypi", "awesome"
    dimension: str = ""  # "functional", "tech_stack", "scenario"
    strategy: str = "default"


class LLMClient:
    """OpenAI API client wrapper for LLM-assisted operations."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        response_format: dict | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Send a chat completion request to OpenAI API."""
        if not self.available:
            raise RuntimeError("OPENAI_API_KEY not set. Cannot use LLM features.")

        async with httpx.AsyncClient(timeout=60) as client:
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format:
                payload["response_format"] = response_format

            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    def _parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON from OpenAI response."""
        content = response["choices"][0]["message"]["content"]
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```json or ```) and last line (```)
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(content)

    # ── Search Query Expansion ──────────────────────────

    async def expand_search_queries(
        self,
        title: str,
        problem_statement: str,
        required_capabilities: list[str],
        preferred_capabilities: list[str] | None = None,
    ) -> list[SearchQueryVariant]:
        """Use LLM to expand a JD into multiple search query variants."""
        if not self.available:
            return self._fallback_queries(title, required_capabilities)

        cap_text = ", ".join(required_capabilities) if required_capabilities else "general MCP tools"
        pref_text = ", ".join(preferred_capabilities) if preferred_capabilities else ""

        prompt = f"""You are a technical recruiter searching for open-source solutions.
Given a job description, generate multiple diverse search queries that would find
candidate projects on GitHub, web search engines, PyPI, and awesome-lists.

Generate queries across these DIMENSIONS:
1. functional: keywords describing core functionality (e.g., "file system access", "database query")
2. tech_stack: technology-specific terms (e.g., "python mcp server", "typescript stdio")
3. scenario: use-case / application scenario terms (e.g., "browser automation tool", "api integration")

For each dimension, generate queries targeting these SOURCES:
- github_topic: GitHub topic/repo search query
- github_code: GitHub code search query (look for actual import statements)
- web: general web search query (Google/DuckDuckGo style)
- pypi: PyPI package search query (if Python relevant)

JOB TITLE: {title}
PROBLEM STATEMENT: {problem_statement}
REQUIRED CAPABILITIES: {cap_text}
PREFERRED CAPABILITIES: {pref_text}

Return a JSON object with a "queries" array. Each entry: {{"query_string": "...", "source_type": "...", "dimension": "..."}}.
Generate at least 8 diverse queries covering all dimension×source combinations that are relevant.
Only include pypi source_type if the domain suggests Python relevance.
"""

        try:
            response = await self._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1500,
                temperature=0.4,
            )
            data = self._parse_json_response(response)
            variants: list[SearchQueryVariant] = []
            for q in data.get("queries", []):
                variants.append(SearchQueryVariant(
                    query_string=q.get("query_string", ""),
                    source_type=q.get("source_type", "web"),
                    dimension=q.get("dimension", "functional"),
                ))
            return variants if variants else self._fallback_queries(title, required_capabilities)
        except Exception:
            return self._fallback_queries(title, required_capabilities)

    def _fallback_queries(
        self, title: str, capabilities: list[str]
    ) -> list[SearchQueryVariant]:
        """Generate fallback queries without LLM."""
        variants: list[SearchQueryVariant] = []
        caps = capabilities if capabilities else ["mcp server"]

        # GitHub topic queries
        for cap in caps[:5]:
            variants.append(SearchQueryVariant(
                query_string=f"topic:mcp {cap}",
                source_type="github_topic",
                dimension="functional",
            ))
        variants.append(SearchQueryVariant(
            query_string="topic:mcp-server stars:>10",
            source_type="github_topic",
            dimension="functional",
        ))
        # Web queries
        for cap in caps[:3]:
            variants.append(SearchQueryVariant(
                query_string=f"best {cap} open source tool 2024 2025",
                source_type="web",
                dimension="functional",
            ))
        # Awesome-list query
        variants.append(SearchQueryVariant(
            query_string="awesome-mcp-servers",
            source_type="awesome",
            dimension="functional",
        ))
        return variants

    # ── JD Generation ────────────────────────────────────

    async def generate_jd(self, user_description: str) -> dict[str, Any]:
        """Generate a structured job description from a free-form description."""
        if not self.available:
            raise RuntimeError("OPENAI_API_KEY not set. Cannot generate JD with LLM.")

        prompt = f"""You are a technical recruiter creating a job description for finding
the best open-source technical solution. Based on the user's requirements below,
generate a structured job description.

USER REQUIREMENTS:
{user_description}

Return a JSON object with these fields:
- title: A concise, descriptive job title (e.g., "Filesystem MCP Server")
- problem_statement: 1-2 sentences describing the problem to solve
- required_capabilities: Array of 3-8 required capability keywords (use English, lowercase)
- preferred_capabilities: Array of 2-5 bonus/nice-to-have keywords (English, lowercase)
- hard_requirements: {{"min_stars": number|null, "max_days_since_update": number|null, "min_tool_count": number|null, "require_license": boolean}}
- suggested_test_scenarios: Array of {{"name": "...", "description": "...", "test_cases": [{{"name": "...", "mcp_tool_name": "...", "expected_behavior": "no_error"}}]}}
- suggested_search_queries: Array of 5-10 search query strings for finding candidates

Be practical and realistic with hard_requirements. For an MCP server, min_stars of 0-50 is reasonable.
For a popular library, 100-500 is reasonable. max_days_since_update should be 180-365.
"""

        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.3,
        )
        return self._parse_json_response(response)
