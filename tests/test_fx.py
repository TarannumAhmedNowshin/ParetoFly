"""Unit tests for currency conversion (FX)."""

from __future__ import annotations

import app.tools.fx as fx
from app.tools.kb_cache import KnowledgeCache
from tests.conftest import make_offers


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, "_CACHE", KnowledgeCache(str(tmp_path / "fx"), 3600))
    fx._MEM.clear()


def test_same_currency_is_identity():
    assert fx.get_fx_rate("USD", "USD") == 1.0


def test_get_fx_rate_from_api(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"rates": {"BDT": 121.5}}

    monkeypatch.setattr(fx.httpx, "get", lambda *a, **k: _Resp())
    assert fx.get_fx_rate("USD", "BDT") == 121.5
    # Second call served from memory even if the network would now fail.
    monkeypatch.setattr(fx.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    assert fx.get_fx_rate("USD", "BDT") == 121.5


def test_get_fx_rate_returns_none_on_failure(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(fx.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    assert fx.get_fx_rate("USD", "BDT") is None


def test_convert_offers_scales_all_money():
    offers = make_offers()
    o = offers[0]
    o.true_price = o.price
    o.student_discount_amount = 40.0
    o.price_breakdown = {"base": o.price, "student_discount": -40.0, "true_price": o.price - 40.0}
    base_price = o.price

    fx.convert_offers(offers, "BDT", 100.0)

    assert o.currency == "BDT"
    assert o.price == round(base_price * 100.0, 2)
    assert o.student_discount_amount == 4000.0
    assert o.price_breakdown["student_discount"] == -4000.0
