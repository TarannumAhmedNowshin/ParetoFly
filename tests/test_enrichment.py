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


def _student_query(bags: int = 0) -> TripQuery:
    return TripQuery(
        origin="DAC",
        destination="JFK",
        depart_date=date(2026, 8, 12),
        adults=1,
        signals=ParsedSignals(checked_bags=bags, is_student=True),
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


def test_student_discount_lowers_true_price(monkeypatch):
    monkeypatch.setattr(
        enrichment,
        "_student_benefit",
        lambda airline, cabin, currency: enrichment._StudentBenefit(amount=40.0),
    )
    offers = make_offers()
    query = _student_query()

    adjusted = enrichment.enrich_true_prices(offers, query)

    assert adjusted == len(offers)
    for offer in offers:
        assert offer.student_discount_amount == 40.0
        assert offer.true_price == offer.price - 40.0
        assert offer.price_breakdown["student_discount"] == -40.0


def test_student_percentage_discount(monkeypatch):
    monkeypatch.setattr(
        enrichment,
        "_student_benefit",
        lambda airline, cabin, currency: enrichment._StudentBenefit(
            percent=10.0, conditional=True, source="Student Club"
        ),
    )
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        expected = offer.price * 0.10
        assert offer.student_discount_percent == 10.0
        assert offer.student_discount_conditional is True
        assert offer.student_discount_amount == expected
        assert offer.true_price == offer.price - expected


def test_student_baggage_bonus_recorded(monkeypatch):
    monkeypatch.setattr(
        enrichment,
        "_student_benefit",
        lambda airline, cabin, currency: enrichment._StudentBenefit(
            percent=10.0, extra_baggage_kg=10.0
        ),
    )
    monkeypatch.setattr(enrichment, "_baggage_allowance", lambda airline, cabin: (1, 7.0))
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.student_baggage_bonus_kg == 10.0
        assert offer.baggage_allowance_kg == 7.0
        assert offer.total_cabin_baggage_kg == 17.0


def test_site_discount_recorded_with_source(monkeypatch):
    monkeypatch.setattr(enrichment, "_site_discount", lambda airline, currency: (25.0, "FlyDeals"))
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.site_discount_amount == 25.0
        assert offer.site_discount_source == "FlyDeals"
        assert offer.true_price == offer.price - 25.0


def test_baggage_allowance_recorded(monkeypatch):
    monkeypatch.setattr(enrichment, "_baggage_allowance", lambda airline, cabin: (1, 8.0))
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.baggage_allowance_pieces == 1
        assert offer.baggage_allowance_kg == 8.0


def test_true_price_never_negative(monkeypatch):
    # A discount larger than the fare must clamp to zero, not go negative.
    monkeypatch.setattr(
        enrichment,
        "_student_benefit",
        lambda airline, cabin, currency: enrichment._StudentBenefit(amount=99999.0),
    )
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.true_price == 0.0


def test_no_bags_no_student_is_noop():
    offers = make_offers()
    query = TripQuery(
        origin="DAC",
        destination="JFK",
        depart_date=date(2026, 8, 12),
        adults=1,
        signals=ParsedSignals(),
    )
    assert enrichment.enrich_true_prices(offers, query) == 0
    assert all(o.true_price is None for o in offers)
