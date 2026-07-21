"""Tests for the SerpAPI response cache and its integration with search_flights."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.config import Settings
from app.models.schemas import TripQuery
from app.tools import serpapi_flights
from app.tools.flight_cache import FlightCache, cache_key
from tests.conftest import make_offers


def _query(**kwargs) -> TripQuery:
    params = dict(origin="DAC", destination="JFK", depart_date=date(2026, 8, 12))
    params.update(kwargs)
    return TripQuery(**params)


def test_cache_key_stable_and_route_sensitive():
    a = _query()
    b = _query()
    assert cache_key(a) == cache_key(b)
    assert cache_key(a) != cache_key(_query(destination="LAX"))
    assert cache_key(a) != cache_key(_query(adults=2))


def test_flight_cache_roundtrip(tmp_path):
    cache = FlightCache(str(tmp_path), ttl_seconds=3600)
    offers = make_offers()
    key = "abc123"
    assert cache.get(key) is None
    cache.set(key, offers)
    loaded = cache.get(key)
    assert loaded is not None
    assert [o.id for o in loaded] == [o.id for o in offers]


def test_flight_cache_expires(tmp_path):
    cache = FlightCache(str(tmp_path), ttl_seconds=0)
    cache.set("k", make_offers())
    # TTL of 0 means any elapsed time is expired.
    assert cache.get("k") is None


def _settings(tmp_path) -> Settings:
    return Settings(
        serpapi_api_key="test-key",
        serpapi_cache_enabled=True,
        serpapi_cache_dir=str(tmp_path),
        serpapi_cache_ttl_seconds=3600,
    )


def test_search_flights_second_call_served_from_cache(tmp_path, monkeypatch):
    """A repeated identical search must not hit SerpAPI again."""

    calls = {"count": 0}

    def fake_get(self, url, params=None):  # noqa: ANN001
        calls["count"] += 1
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(
            200,
            json={
                "best_flights": [
                    {
                        "flights": [
                            {
                                "departure_airport": {"id": "DAC", "time": "2026-08-12 02:00"},
                                "arrival_airport": {"id": "JFK", "time": "2026-08-12 14:15"},
                                "airline": "Qatar Airways",
                                "flight_number": "QR701",
                                "airplane": "Boeing 777",
                                "duration": 735,
                            }
                        ],
                        "total_duration": 735,
                        "price": 912,
                    }
                ]
            },
            request=request,
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    settings = _settings(tmp_path)
    query = _query()

    first = serpapi_flights.search_flights(query, settings=settings)
    second = serpapi_flights.search_flights(query, settings=settings)

    assert calls["count"] == 1  # second call served from cache
    assert len(first) == 1
    assert [o.id for o in first] == [o.id for o in second]


def test_search_flights_use_cache_false_forces_live(tmp_path, monkeypatch):
    calls = {"count": 0}

    def fake_get(self, url, params=None):  # noqa: ANN001
        calls["count"] += 1
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"best_flights": []}, request=request)

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    settings = _settings(tmp_path)
    query = _query()

    serpapi_flights.search_flights(query, settings=settings, use_cache=False)
    serpapi_flights.search_flights(query, settings=settings, use_cache=False)
    assert calls["count"] == 2
