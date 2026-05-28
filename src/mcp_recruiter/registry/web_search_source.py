"""Web search source — find candidates via DuckDuckGo / general web search."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from ..core.enums import RegistrySource
from .base import RawCandidate, RegistrySource as AbstractRegistrySource


class WebSearchSource(AbstractRegistrySource):
    """Search the web for open-source project candidates.

    Uses DuckDuckGo's Instant Answer API (no API key required) for
    free-text web search, then extracts candidate metadata from results.
    """

    DDG_API = "https://api.duckduckgo.com"
    # Fallback: use a simple HTML search if DuckDuckGo API is insufficient
    SEARCH_URLS = [
        "https://html.duckduckgo.com/html/",
    ]

    @property
    def source_type(self) -> RegistrySource:
        return RegistrySource.WEB_SEARCH

    async def search(self, query: str, limit: int = 20) -> list[RawCandidate]:
        """Search the web for candidates matching the query."""
        candidates: list[RawCandidate] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Try DuckDuckGo Instant Answer API first
            try:
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1",
                }
                resp = await client.get(self.DDG_API, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    # Extract from RelatedTopics and Results
                    extracted = self._parse_ddg_response(data, query)
                    candidates.extend(extracted)
            except httpx.HTTPError:
                pass

            # If DuckDuckGo returned nothing useful, try HTML search
            if not candidates:
                try:
                    form_data = {"q": query}
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    resp = await client.post(
                        self.SEARCH_URLS[0],
                        data=form_data,
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        extracted = self._parse_ddg_html(resp.text, query)
                        candidates.extend(extracted)
                except httpx.HTTPError:
                    pass

        return candidates[:limit]

    async def fetch_details(self, candidate: RawCandidate) -> dict[str, Any]:
        """Fetch additional details from the candidate's URL."""
        details: dict[str, Any] = {"readme": "", "contributors_count": 0}

        if not candidate.url:
            return details

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = await client.get(candidate.url, headers=headers)
                if resp.status_code == 200:
                    details["readme"] = resp.text[:10000]  # first 10KB
        except httpx.HTTPError:
            pass

        return details

    def _parse_ddg_response(self, data: dict, query: str) -> list[RawCandidate]:
        """Parse DuckDuckGo JSON API response."""
        candidates: list[RawCandidate] = []

        # Abstract / answer
        abstract = data.get("AbstractText", "")
        abstract_url = data.get("AbstractURL", "")
        if abstract and abstract_url:
            name = self._extract_name_from_url(abstract_url)
            candidates.append(RawCandidate(
                source=RegistrySource.WEB_SEARCH,
                identifier=abstract_url,
                name=name,
                description=abstract[:500],
                url=abstract_url,
            ))

        # Related topics
        for topic in data.get("RelatedTopics", [])[:15]:
            text = topic.get("Text", "") if isinstance(topic, dict) else ""
            url = topic.get("FirstURL", "") if isinstance(topic, dict) else ""
            if text and url:
                name = self._extract_name_from_url(url)
                candidates.append(RawCandidate(
                    source=RegistrySource.WEB_SEARCH,
                    identifier=url,
                    name=name,
                    description=text[:500],
                    url=url,
                ))

        return candidates

    def _parse_ddg_html(self, html: str, query: str) -> list[RawCandidate]:
        """Parse DuckDuckGo HTML search results."""
        candidates: list[RawCandidate] = []

        # Extract result links and snippets
        link_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        seen: set[str] = set()
        for i, (url, title) in enumerate(links[:20]):
            clean_url = self._clean_url(url)
            if clean_url in seen:
                continue
            seen.add(clean_url)

            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippets[i] if i < len(snippets) else "").strip()

            if clean_title:
                candidates.append(RawCandidate(
                    source=RegistrySource.WEB_SEARCH,
                    identifier=clean_url,
                    name=clean_title,
                    description=snippet[:500],
                    url=clean_url,
                ))

        return candidates

    @staticmethod
    def _extract_name_from_url(url: str) -> str:
        """Extract a readable name from a URL."""
        # Remove protocol and www
        cleaned = re.sub(r'^https?://(www\.)?', '', url)
        # Take first path segment
        parts = cleaned.split('/')
        domain = parts[0].rstrip('.com').rstrip('.org').rstrip('.io').rstrip('.dev')
        if len(parts) > 1 and parts[-1]:
            return parts[-1].replace('-', ' ').replace('_', ' ').title()
        return domain.replace('-', ' ').title()

    @staticmethod
    def _clean_url(url: str) -> str:
        """Clean a URL extracted from HTML."""
        url = url.strip()
        # Remove DuckDuckGo redirect wrapper
        if 'uddg=' in url:
            from urllib.parse import unquote
            match = re.search(r'uddg=([^&]+)', url)
            if match:
                url = unquote(match.group(1))
        return url
