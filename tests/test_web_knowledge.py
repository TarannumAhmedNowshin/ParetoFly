"""Unit tests for the web-knowledge provider chain + circuit breaker."""

from __future__ import annotations

import pytest

import app.tools.web_knowledge as wk


@pytest.fixture(autouse=True)
def _reset():
    wk.reset_health()
    wk.reset_status()
    # Exclude Playwright by default so tests don't launch a browser.
    yield


def test_serper_is_used_first(monkeypatch):
    monkeypatch.setattr(wk, "_playwright_available", lambda: False)
    monkeypatch.setattr(wk, "_serper_search", lambda q, n, s: ["serper snippet"])
    monkeypatch.setattr(wk, "_duckduckgo_search", lambda q, n, s: ["ddg snippet"])

    out = wk.get_web_snippets("qatar baggage")
    assert out == ["serper snippet"]
    assert wk.last_status().provider == "serper"


def test_falls_back_to_duckduckgo_when_serper_fails(monkeypatch):
    monkeypatch.setattr(wk, "_playwright_available", lambda: False)

    def _boom(q, n, s):
        raise RuntimeError("403")

    monkeypatch.setattr(wk, "_serper_search", _boom)
    monkeypatch.setattr(wk, "_duckduckgo_search", lambda q, n, s: ["ddg snippet"])

    out = wk.get_web_snippets("qatar baggage")
    assert out == ["ddg snippet"]
    assert wk.last_status().provider == "duckduckgo"


def test_circuit_breaker_skips_failed_provider(monkeypatch):
    monkeypatch.setattr(wk, "_playwright_available", lambda: False)
    calls = {"serper": 0}

    def _boom(q, n, s):
        calls["serper"] += 1
        raise RuntimeError("403")

    monkeypatch.setattr(wk, "_serper_search", _boom)
    monkeypatch.setattr(wk, "_duckduckgo_search", lambda q, n, s: ["ddg"])

    wk.get_web_snippets("q1")
    wk.get_web_snippets("q2")
    # Serper tripped on the first call and is skipped on the second.
    assert calls["serper"] == 1


def test_playwright_used_when_others_fail(monkeypatch):
    monkeypatch.setattr(wk, "_playwright_available", lambda: True)
    monkeypatch.setattr(wk, "_serper_search", lambda q, n, s: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(wk, "_duckduckgo_search", lambda q, n, s: [])
    monkeypatch.setattr(wk, "_playwright_search", lambda q, n, s: ["browser snippet"])

    out = wk.get_web_snippets("qatar baggage")
    assert out == ["browser snippet"]
    assert wk.last_status().provider == "playwright"


def test_all_providers_fail_returns_empty(monkeypatch):
    monkeypatch.setattr(wk, "_playwright_available", lambda: False)
    monkeypatch.setattr(wk, "_serper_search", lambda q, n, s: [])
    monkeypatch.setattr(wk, "_duckduckgo_search", lambda q, n, s: [])

    out = wk.get_web_snippets("qatar baggage")
    assert out == []
    assert wk.last_status().all_failed is True
