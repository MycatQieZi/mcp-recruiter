"""Registry cache layer — simple JSON-file-based TTL cache."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class RegistryCache:
    """TTL-based cache for registry search results."""

    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, source: str, query: str) -> list[dict] | None:
        key = self._make_key(source, query)
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if time.time() - data.get("cached_at", 0) > data.get("ttl", 3600):
            return None
        return data.get("results", [])

    def set(self, source: str, query: str, results: list[dict], ttl: int = 3600) -> None:
        key = self._make_key(source, query)
        data = {"source": source, "query": query, "cached_at": time.time(), "ttl": ttl, "results": results}
        (self.cache_dir / f"{key}.json").write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8"
        )

    def clear(self) -> None:
        for f in self.cache_dir.glob("*.json"):
            f.unlink()

    @staticmethod
    def _make_key(source: str, query: str) -> str:
        return hashlib.md5(f"{source}:{query}".encode()).hexdigest()[:12]
