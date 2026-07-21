"""Unit tests for true-cost (baggage) enrichment."""

from __future__ import annotations

from datetime import date

import app.enrichment as enrichment
from app.models.schemas import ParsedSignals, TripQuery
from tests.conftest import make_offers


def _query_with_bags(bags: int) -> TripQuery:
    return TripQuery(
        origin="DAC",
        destination="JFK",
        depart_date=date(2026, 8, 12),
        adults=1,
        signals=ParsedSignals(checked_bags=bags),
    )


def test_no_bags_is_a_noop():
    offers = make_offers()
    adjusted = enrichment.enrich_true_prices(offers, _query_with_bags(0))
    assert adjusted == 0
    assert all(o.true_price is None for o in offers)


def test_bags_add_fee_to_true_price(monkeypatch):
    # Fixture offers carry no baggage-included extension -> all get charged.
    monkeypatch.setattr(enrichment, "_first_checked_bag_fee", lambda airline, currency: 50.0)
    offers = make_offers()
    query = _query_with_bags(2)

    adjusted = enrichment.enrich_true_prices(offers, query)

    assert adjusted == len(offers)
    for offer in offers:
        assert offer.true_price == offer.price + 2 * 1 * 50.0
        assert offer.effective_price == offer.true_price


def test_included_baggage_not_charged(monkeypatch):
    monkeypatch.setattr(enrichment, "_first_checked_bag_fee", lambda airline, currency: 50.0)
    offers = make_offers()
    offers[0].extensions = ["1 checked bag included"]
    query = _query_with_bags(1)

    enrichment.enrich_true_prices(offers, query)

    # The included-bag offer keeps its base price.
    assert offers[0].true_price == offers[0].price
