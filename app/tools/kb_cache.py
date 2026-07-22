"""Persistent, TTL-bounded cache for enriched airline knowledge.

Discount/baggage facts (baggage fees, student programs, cabin allowances) change
slowly, but each lookup is an expensive web-search + LLM round-trip. We cache the
extracted result on disk (surviving restarts) so repeat queries and repeat
airlines cost nothing. Keyed by an opaque string the caller builds.

Stdlib-only (one JSON file per key) to avoid extra dependencies, mirroring
:class:`app.tools.flight_cache.FlightCache`.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional


def kb_key(*parts: str) -> str:
    """Build a stable filesystem-safe key from arbitrary string parts."""

    raw = "|".join(p.strip().lower() for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class KnowledgeCache:
    """A tiny persistent TTL cache storing JSON-serializable dicts on disk."""

    def __init__(self, directory: str, ttl_seconds: int) -> None:
        self._dir = Path(directory)
        self._ttl = ttl_seconds

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, key: str) -> Optional[dict[str, Any]]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - payload.get("ts", 0) > self._ttl:
            return None
        value = payload.get("value")
        return value if isinstance(value, dict) else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = {"ts": time.time(), "value": value}
        tmp = self._path(key).with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._path(key))
        except OSError:
            # Caching is best-effort; never fail enrichment over disk issues.
            if tmp.exists():
                tmp.unlink(missing_ok=True)
