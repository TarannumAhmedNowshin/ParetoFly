"""SerpAPI Google Flights client.

Wraps the ``google_flights`` engine and normalizes its response into our
:class:`~app.models.schemas.FlightOffer` list. The engine returns two arrays,
``best_flights`` and ``other_flights`` (identical shape); we merge both.

Reference response fields used:
``flights[]`` (segments), ``layovers[]``, ``total_duration``, ``price``,
``carbon_emissions.this_flight``, ``type``, ``airline_logo``, ``booking_token``.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Optional

import httpx

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.models.schemas import FlightOffer, FlightSegment, Layover, TripQuery
from app.tools.flight_cache import FlightCache, cache_key

_DELAY_FLAG = "often_delayed_by_over_30_min"

log = get_logger("tools.serpapi")


def _redact(text: str) -> str:
    """Strip the api_key value from any string before it reaches logs/errors."""

    return re.sub(r"(api_key=)[^&\s]+", r"\1<redacted>", text)


class SerpApiError(RuntimeError):
    """Raised when the SerpAPI request fails or returns an error payload."""


def _parse_dt(value: str) -> datetime:
    # SerpAPI returns "2026-08-12 14:15" (local airport time, no tz).
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def _segment_from_json(raw: dict[str, Any]) -> FlightSegment:
    dep = raw["departure_airport"]
    arr = raw["arrival_airport"]
    return FlightSegment(
        departure_airport=dep["id"],
        departure_time=_parse_dt(dep["time"]),
        arrival_airport=arr["id"],
        arrival_time=_parse_dt(arr["time"]),
        airline=raw.get("airline", "Unknown"),
        flight_number=raw.get("flight_number", ""),
        aircraft=raw.get("airplane"),
        cabin=raw.get("travel_class"),
        duration_minutes=int(raw.get("duration", 0)),
        legroom=raw.get("legroom"),
        often_delayed=bool(raw.get(_DELAY_FLAG, False)),
        extensions=list(raw.get("extensions", [])),
    )


def _layover_from_json(raw: dict[str, Any]) -> Layover:
    return Layover(
        airport=raw.get("id", raw.get("name", "")),
        duration_minutes=int(raw.get("duration", 0)),
        overnight=bool(raw.get("overnight", False)),
    )


def _make_offer_id(segments: list[FlightSegment], price: float, token: Optional[str]) -> str:
    if token:
        return hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]
    seed = "|".join(f"{s.airline}{s.flight_number}{s.departure_time.isoformat()}" for s in segments)
    seed += f"|{price}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _offer_from_json(raw: dict[str, Any]) -> FlightOffer:
    segments = [_segment_from_json(s) for s in raw.get("flights", [])]
    layovers = [_layover_from_json(l) for l in raw.get("layovers", [])]
    price = float(raw.get("price", 0) or 0)
    token = raw.get("booking_token")
    carbon = (raw.get("carbon_emissions") or {}).get("this_flight")
    return FlightOffer(
        id=_make_offer_id(segments, price, token),
        segments=segments,
        layovers=layovers,
        total_duration_minutes=int(raw.get("total_duration", 0)),
        price=price,
        currency=raw.get("_currency", "USD"),
        carbon_emissions_g=int(carbon) if carbon is not None else None,
        trip_type=raw.get("type"),
        airline_logo=raw.get("airline_logo"),
        booking_token=token,
        extensions=list(raw.get("extensions", [])),
    )


def _build_params(query: TripQuery, settings: Settings) -> dict[str, Any]:
    params: dict[str, Any] = {
        "engine": "google_flights",
        "departure_id": query.origin,
        "arrival_id": query.destination,
        "outbound_date": query.depart_date.isoformat(),
        "currency": query.currency,
        "travel_class": query.cabin.serpapi_code,
        "adults": query.adults,
        "hl": "en",
        "api_key": settings.serpapi_api_key,
    }
    if query.is_round_trip:
        params["type"] = 1
        params["return_date"] = query.return_date.isoformat()
    else:
        params["type"] = 2
    if query.children:
        params["children"] = query.children
    if query.infants:
        params["infants_in_seat"] = query.infants
    # Advanced filters
    if query.max_stops is not None:
        # SerpAPI: 0=any, 1=nonstop, 2=<=1 stop, 3=<=2 stops
        params["stops"] = min(query.max_stops + 1, 3) if query.max_stops <= 2 else 0
    if query.budget is not None:
        params["max_price"] = int(query.budget)
    if query.excluded_airlines:
        params["exclude_airlines"] = ",".join(query.excluded_airlines)
    elif query.preferred_airlines:
        params["include_airlines"] = ",".join(query.preferred_airlines)
    return params


def _extract_offers(payload: dict[str, Any], currency: str) -> list[FlightOffer]:
    raw_offers: list[dict[str, Any]] = []
    raw_offers.extend(payload.get("best_flights") or [])
    raw_offers.extend(payload.get("other_flights") or [])
    offers: list[FlightOffer] = []
    for raw in raw_offers:
        if not raw.get("flights"):
            continue
        price = raw.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            # Google Flights omits the price for unbookable/unavailable fares.
            # A 0 price would masquerade as the cheapest option, so skip it.
            airline = (raw["flights"][0] or {}).get("airline", "Unknown")
            log.debug("serpapi: skipping offer with missing/zero price (airline=%s)", airline)
            continue
        raw["_currency"] = currency
        offers.append(_offer_from_json(raw))
    return offers


def search_flights(
    query: TripQuery,
    *,
    settings: Optional[Settings] = None,
    client: Optional[httpx.Client] = None,
    timeout: float = 30.0,
    use_cache: bool = True,
) -> list[FlightOffer]:
    """Search Google Flights via SerpAPI and return normalized offers.

    Results are cached on disk (keyed by the request parameters) to protect the
    limited free-tier search quota. Pass ``use_cache=False`` to force a live call.

    Raises :class:`SerpApiError` on transport or API-level errors.
    """

    settings = settings or get_settings()
    if not settings.serpapi_api_key:
        raise SerpApiError("SERPAPI_API_KEY / SerpApi_key is not configured in .env")

    caching = use_cache and settings.serpapi_cache_enabled
    cache: Optional[FlightCache] = None
    key = ""
    if caching:
        cache = FlightCache(settings.serpapi_cache_dir, settings.serpapi_cache_ttl_seconds)
        key = cache_key(query)
        cached = cache.get(key)
        if cached is not None:
            log.info(
                "serpapi: CACHE HIT %s->%s %s (%d offers, key=%s)",
                query.origin, query.destination, query.depart_date, len(cached), key,
            )
            return cached

    params = _build_params(query, settings)
    result_currency = query.currency
    log.info(
        "serpapi: live request %s->%s depart=%s currency=%s cabin=%s type=%s (cache_%s)",
        query.origin, query.destination, query.depart_date, query.currency,
        query.cabin.serpapi_code, params.get("type"),
        "miss" if caching else "off",
    )

    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        try:
            response = client.get(settings.serpapi_base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            # Google Flights rejects some currencies (e.g. BDT) with HTTP 400.
            # Retry once in USD so the traveler still gets fares instead of nothing.
            if exc.response.status_code == 400 and query.currency.upper() != "USD":
                log.warning(
                    "serpapi: HTTP 400 for currency=%s, retrying in USD", query.currency,
                )
                params["currency"] = "USD"
                result_currency = "USD"
                response = client.get(settings.serpapi_base_url, params=params)
                response.raise_for_status()
                payload = response.json()
            else:
                raise
    except httpx.HTTPError as exc:
        log.error("serpapi: request failed: %s", _redact(str(exc)))
        raise SerpApiError(f"SerpAPI request failed: {_redact(str(exc))}") from exc
    finally:
        if owns_client:
            client.close()

    if payload.get("error"):
        log.error("serpapi: API error payload: %s", _redact(str(payload["error"])))
        raise SerpApiError(_redact(str(payload["error"])))

    offers = _extract_offers(payload, result_currency)
    log.info("serpapi: parsed %d offers (currency=%s)", len(offers), result_currency)
    if cache is not None and offers:
        cache.set(key, offers)
        log.debug("serpapi: cached %d offers under key=%s", len(offers), key)
    return offers
