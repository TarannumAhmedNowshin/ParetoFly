"""Persistent per-day budget guard for the limited SerpAPI free tier.

Only *live* searches consume the monthly quota (cache hits do not), so the
counter is bumped from :func:`app.tools.serpapi_flights.search_flights` right
after a successful live request. The count is persisted to a small JSON file so
it survives process restarts within a deployment; it resets each calendar day.
``serpapi_daily_budget = 0`` disables the guard entirely (local dev / tests).
"""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

from app.config import get_settings
from app.logging_config import get_logger

log = get_logger("budget")

_LOCK = threading.Lock()


def _budget_file() -> Path:
    directory = Path(get_settings().serpapi_cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "_daily_budget.json"


def _load() -> tuple[str, int]:
    try:
        data = json.loads(_budget_file().read_text(encoding="utf-8"))
        return str(data.get("date", "")), int(data.get("count", 0))
    except Exception:
        return "", 0


def serpapi_budget_exhausted() -> bool:
    """True when today's live-search budget is already spent (0 = unlimited)."""

    limit = get_settings().serpapi_daily_budget
    if limit <= 0:
        return False
    with _LOCK:
        day, count = _load()
    return day == date.today().isoformat() and count >= limit


def note_serpapi_search() -> None:
    """Record one consumed live SerpAPI search; the tally resets each day."""

    if get_settings().serpapi_daily_budget <= 0:
        return
    today = date.today().isoformat()
    with _LOCK:
        day, count = _load()
        count = count + 1 if day == today else 1
        try:
            _budget_file().write_text(
                json.dumps({"date": today, "count": count}), encoding="utf-8"
            )
        except Exception:  # pragma: no cover - budget persistence must not break search
            log.warning("budget: could not persist daily counter")
