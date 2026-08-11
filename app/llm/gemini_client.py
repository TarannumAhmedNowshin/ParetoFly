"""Factories for the two Gemini tiers, backed by a single free API key.

- ``get_mini_llm``  -> intake parsing, clarify, extraction (cheap, high-volume).
- ``get_full_llm``  -> narrative / explain node (quality).

Free-tier survival strategy
---------------------------
The Gemini free tier is generous on tokens but strict on *requests per minute*.
The enrichment node fans out one call per airline concurrently, so a busy search
can burst well past the cap. Two guards keep us inside it:

1. A **shared** :class:`InMemoryRateLimiter` throttles *every* Gemini call in the
   process — including the concurrent enrichment threads — to a steady RPM. This
   prevents most 429s before they happen instead of reacting to them.
2. ``max_retries`` adds exponential backoff for the 429s that still slip through
   (e.g. daily-quota pressure), after which each call site falls back to its
   rule-based / form-derived path rather than crashing the search.

Both clients are cached so we reuse one instance — and therefore one rate-limit
bucket — per process.
"""

from __future__ import annotations

import contextvars
from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings


# --- Free-tier 429 tracking -------------------------------------------------
# A search fires several Gemini calls (intake, per-airline enrichment, explain).
# When the free-tier daily/RPM quota is exhausted they 429 and each call site
# falls back gracefully — but we still want to *tell* the traveler. Each node
# seeds a fresh mutable flag in the current context before its LLM work; the
# enrichment fan-out shares that same flag object because it copies the context
# into its worker threads, so a 429 raised on any thread is visible afterwards.

RATE_LIMIT_NOTICE = (
    "ParetoFly is an open-source project and we run on a free AI tier, which "
    "we've hit for the moment. Give it a few minutes and search again for the "
    "richer AI insights."
)


class _RateLimitFlag:
    __slots__ = ("hit",)

    def __init__(self) -> None:
        self.hit = False


_rl_flag: contextvars.ContextVar[_RateLimitFlag | None] = contextvars.ContextVar(
    "paretofly_rate_limit", default=None
)


def begin_llm_call_tracking() -> None:
    """Start a fresh rate-limit tally for the current node's LLM work."""

    _rl_flag.set(_RateLimitFlag())


def note_rate_limit() -> None:
    """Record that a Gemini call in this context hit its quota (a 429)."""

    flag = _rl_flag.get()
    if flag is not None:
        flag.hit = True


def llm_rate_limited() -> bool:
    """True if any tracked Gemini call in this context was rate-limited."""

    flag = _rl_flag.get()
    return bool(flag and flag.hit)


def is_rate_limit_error(exc: BaseException) -> bool:
    """Heuristically detect a Gemini free-tier quota / 429 error."""

    text = f"{type(exc).__name__} {exc}".lower()
    return (
        "resource_exhausted" in text
        or "429" in text
        or "rate limit" in text
        or "ratelimit" in text
        or "quota" in text
    )


@lru_cache(maxsize=1)
def _rate_limiter() -> InMemoryRateLimiter:
    """One bucket shared by every Gemini call to respect the free-tier RPM cap."""

    rpm = max(1.0, get_settings().gemini_requests_per_minute)
    return InMemoryRateLimiter(
        requests_per_second=rpm / 60.0,
        # Wake often so threads waiting on the bucket acquire promptly.
        check_every_n_seconds=0.1,
        # Allow a small burst but never more than ~one minute of budget at once.
        max_bucket_size=rpm,
    )


@lru_cache(maxsize=1)
def get_mini_llm() -> ChatGoogleGenerativeAI:
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model=s.gemini_mini_model,
        google_api_key=s.gemini_api_key,
        # Extraction should be deterministic.
        temperature=0.0,
        timeout=s.gemini_timeout,
        max_retries=s.gemini_max_retries,
        rate_limiter=_rate_limiter(),
    )


@lru_cache(maxsize=1)
def get_full_llm() -> ChatGoogleGenerativeAI:
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model=s.gemini_full_model,
        google_api_key=s.gemini_api_key,
        # A little warmth for the narrative prose.
        temperature=0.7,
        timeout=s.gemini_timeout,
        max_retries=s.gemini_max_retries,
        rate_limiter=_rate_limiter(),
    )
