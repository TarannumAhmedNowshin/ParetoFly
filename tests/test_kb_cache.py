"""Unit tests for the persistent knowledge cache."""

from __future__ import annotations

from app.tools.kb_cache import KnowledgeCache, kb_key


def test_set_get_roundtrip(tmp_path):
    cache = KnowledgeCache(str(tmp_path), ttl_seconds=3600)
    key = kb_key("facts", "Qatar Airways", "economy", "USD")
    cache.set(key, {"checked_bag_fee": 55.0})
    assert cache.get(key) == {"checked_bag_fee": 55.0}


def test_missing_key_returns_none(tmp_path):
    cache = KnowledgeCache(str(tmp_path), ttl_seconds=3600)
    assert cache.get(kb_key("nope")) is None


def test_expired_entry_returns_none(tmp_path):
    cache = KnowledgeCache(str(tmp_path), ttl_seconds=0)
    key = kb_key("facts", "x")
    cache.set(key, {"v": 1})
    assert cache.get(key) is None  # ttl=0 -> immediately stale


def test_key_is_stable_and_case_insensitive():
    assert kb_key("A", "B") == kb_key("a", "b")
    assert kb_key("A", "B") != kb_key("A", "C")
