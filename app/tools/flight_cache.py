"""Persistent, TTL-bounded cache for SerpAPI flight results.

The SerpAPI free tier allows only ~250 searches/month, so we cache normalized
offer lists on disk (surviving process restarts during development). Entries are
keyed by the request parameters that actually change the result set and expire
after a configurable TTL.

Implementation is stdlib-only (JSON file per key) to avoid extra dependencies.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from app.models.schemas import FlightOffer, TripQuery


def cache_key(query: TripQuery) -> str:
    """Build a stable key from every field that affects SerpAPI results."""

    parts = [
        query.origin,
        query.destination,
        query.depart_date.isoformat(),
        query.return_date.isoformat() if query.return_date else "OW",
        str(query.adults),
        str(query.children),
        str(query.infants),
        query.cabin.value,
        query.currency,
        str(query.max_stops),
        str(int(query.budget)) if query.budget is not None else "-",
        ",".join(sorted(query.preferred_airlines)),
        ",".join(sorted(query.excluded_airlines)),
    ]
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class FlightCache:
    """A tiny persistent TTL cache storing ``list[FlightOffer]`` as JSON files."""

    def __init__(self, directory: str, ttl_seconds: int) -> None:
        self._dir = Path(directory)
        self._ttl = ttl_seconds

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, key: str) -> Optional[list[FlightOffer]]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - payload.get("ts", 0) > self._ttl:
            return None
        try:
            return [FlightOffer.model_validate(o) for o in payload.get("offers", [])]
        except Exception:
            return None

    def set(self, key: str, offers: list[FlightOffer]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.time(),
            "offers": [o.model_dump(mode="json") for o in offers],
        }
        tmp = self._path(key).with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._path(key))
        except OSError:
            # Caching is best-effort; never fail a search because of disk issues.
            if tmp.exists():
                tmp.unlink(missing_ok=True)
