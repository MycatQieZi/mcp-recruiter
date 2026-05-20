"""Abstract registry source interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..core.enums import RegistrySource


@dataclass
class RawCandidate:
    """Raw metadata for a candidate discovered from a registry."""

    source: RegistrySource
    identifier: str  # unique within source (repo full_name, package name, etc.)
    name: str
    description: str = ""
    url: str = ""
    stars: int = 0
    language: str = ""
    topics: list[str] = field(default_factory=list)
    last_updated: datetime | None = None
    open_issues: int = 0
    license: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


class RegistrySource(ABC):
    """Interface for a candidate discovery data source."""

    @property
    @abstractmethod
    def source_type(self) -> RegistrySource:
        """Return the enum identifying this source."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[RawCandidate]:
        """Search for candidates matching the query."""
        ...

    @abstractmethod
    async def fetch_details(self, candidate: RawCandidate) -> dict[str, Any]:
        """Fetch detailed metadata for a single candidate."""
        ...

    def rate_limit_info(self) -> dict[str, Any]:
        """Return rate limit information for this source."""
        return {}
