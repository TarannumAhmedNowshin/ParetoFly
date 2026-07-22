"""Currency conversion via a free, keyless FX rate API (open.er-api.com).

Google Flights (SerpAPI) only supports a subset of currencies, so a search may
fall back to a supported currency (USD). This module converts the resulting
fares to the traveler's requested currency. Rates are cached on disk for a few
hours since intraday FX drift is immaterial for fare display.
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.models.schemas import FlightOffer
from app.tools.kb_cache import KnowledgeCache, kb_key

_MEM: dict[tuple[str, str], float] = {}
_CACHE: Optional[KnowledgeCache] = None

log = get_logger("tools.fx")


def _cache() -> KnowledgeCache:
    global _CACHE
    if _CACHE is None:
        s = get_settings()
        _CACHE = KnowledgeCache(s.fx_cache_dir, s.fx_cache_ttl_seconds)
    return _CACHE


def get_fx_rate(base: str, target: str, *, settings: Optional[Settings] = None) -> Optional[float]:
    """Return units of ``target`` per 1 ``base`` (memory -> disk -> live API).

    Returns ``None`` when the rate cannot be determined (caller should keep the
    original currency rather than guess).
    """

    base, target = base.upper(), target.upper()
    if base == target:
        return 1.0

    key = (base, target)
    if key in _MEM:
        return _MEM[key]

    settings = settings or get_settings()
    disk_key = kb_key("fx_v1", base, target)
    hit = _cache().get(disk_key)
    if hit and isinstance(hit.get("rate"), (int, float)):
        _MEM[key] = float(hit["rate"])
        return _MEM[key]

    try:
        resp = httpx.get(f"{settings.fx_api_base}/{base}", timeout=settings.web_search_timeout)
        resp.raise_for_status()
        rate = (resp.json().get("rates") or {}).get(target)
    except Exception as exc:  # pragma: no cover - network failure -> no conversion
        log.warning("fx: rate lookup %s->%s failed (%s)", base, target, exc)
        return None

    if not rate or rate <= 0:
        log.warning("fx: no rate for %s->%s in API response", base, target)
        return None
    rate = float(rate)
    _cache().set(disk_key, {"rate": rate})
    _MEM[key] = rate
    log.info("fx: %s->%s = %.4f (live)", base, target, rate)
    return rate


def convert_offers(offers: list[FlightOffer], target: str, rate: float) -> None:
    """Convert every monetary field on ``offers`` in place and set the currency."""

    def conv(v: Optional[float]) -> Optional[float]:
        return round(v * rate, 2) if v is not None else None

    for o in offers:
        o.price = round(o.price * rate, 2)
        o.true_price = conv(o.true_price)
        o.student_discount_amount = conv(o.student_discount_amount)
        o.site_discount_amount = conv(o.site_discount_amount)
        if o.price_breakdown:
            o.price_breakdown = {k: round(v * rate, 2) for k, v in o.price_breakdown.items()}
        o.currency = target
