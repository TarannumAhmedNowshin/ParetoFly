"""Unit tests for true-cost enrichment (consolidated airline-facts model)."""

from __future__ import annotations

from datetime import date

import app.enrichment as enrichment
from app.enrichment import _AirlineFacts
from app.models.schemas import ParsedSignals, TripQuery
from app.tools.web_knowledge import WebSnippet
from tests.conftest import make_offers


def _facts(**kwargs):
    """Return a patch callable that yields the same facts for every airline."""

    return lambda airline, cabin, currency: _AirlineFacts(**kwargs)


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
    monkeypatch.setattr(enrichment, "_airline_facts", _facts(checked_bag_fee=50.0))
    offers = make_offers()
    query = _query_with_bags(2)

    adjusted = enrichment.enrich_true_prices(offers, query)

    assert adjusted == len(offers)
    for offer in offers:
        assert offer.true_price == offer.price + 2 * 1 * 50.0
        assert offer.effective_price == offer.true_price


def test_missing_fee_falls_back_to_default(monkeypatch):
    # No web data -> empty facts -> conservative default fee is applied.
    monkeypatch.setattr(enrichment, "_airline_facts", _facts())
    offers = make_offers()
    query = _query_with_bags(1)

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.true_price == offer.price + enrichment._DEFAULT_FEE_USD


def test_included_baggage_not_charged(monkeypatch):
    monkeypatch.setattr(enrichment, "_airline_facts", _facts(checked_bag_fee=50.0))
    offers = make_offers()
    offers[0].extensions = ["1 checked bag included"]
    query = _query_with_bags(1)

    enrichment.enrich_true_prices(offers, query)

    # The included-bag offer keeps its base price.
    assert offers[0].true_price == offers[0].price


def test_student_discount_lowers_true_price(monkeypatch):
    monkeypatch.setattr(enrichment, "_airline_facts", _facts(student_discount_amount=40.0))
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
        "_airline_facts",
        _facts(student_discount_percent=10.0, student_conditional=True),
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
        "_airline_facts",
        _facts(student_discount_percent=10.0, student_extra_baggage_kg=10.0, cabin_baggage_kg=7.0),
    )
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.student_baggage_bonus_kg == 10.0
        assert offer.baggage_allowance_kg == 7.0
        assert offer.total_cabin_baggage_kg == 17.0


def test_site_discount_recorded_with_source(monkeypatch):
    monkeypatch.setattr(
        enrichment,
        "_airline_facts",
        _facts(site_discount_amount=25.0, site_discount_source="FlyDeals"),
    )
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.site_discount_amount == 25.0
        assert offer.site_discount_source == "FlyDeals"
        assert offer.true_price == offer.price - 25.0


def test_baggage_allowance_recorded(monkeypatch):
    monkeypatch.setattr(
        enrichment, "_airline_facts", _facts(cabin_baggage_pieces=1, cabin_baggage_kg=8.0)
    )
    offers = make_offers()
    query = _student_query()

    enrichment.enrich_true_prices(offers, query)

    for offer in offers:
        assert offer.baggage_allowance_pieces == 1
        assert offer.baggage_allowance_kg == 8.0


def test_true_price_never_negative(monkeypatch):
    # A discount larger than the fare must clamp to zero, not go negative.
    monkeypatch.setattr(enrichment, "_airline_facts", _facts(student_discount_amount=99999.0))
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


def test_airline_facts_uses_cache(monkeypatch):
    # A cached (in-memory) fact should short-circuit the live fetch.
    calls = {"n": 0}

    def _fetch(airline, cabin, currency):
        calls["n"] += 1
        return _AirlineFacts(checked_bag_fee=33.0), True

    monkeypatch.setattr(enrichment, "_fetch_airline_facts", _fetch)
    enrichment._MEM.clear()

    a = enrichment._airline_facts("Qatar Airways", "economy", "USD")
    b = enrichment._airline_facts("Qatar Airways", "economy", "USD")
    assert a.checked_bag_fee == 33.0 and b.checked_bag_fee == 33.0
    assert calls["n"] == 1  # second call served from memory


def test_verify_accepts_official_single_source():
    docs = [WebSnippet("Student Club: save 10% on your first flight", "https://www.qatarairways.com/en/student-club.html")]
    facts = _AirlineFacts(
        student_discount_percent=10.0,
        student_discount_evidence="save 10% on your first flight",
        student_discount_support=[1],
        student_discount_confidence=0.9,
    )
    out = enrichment._verify(facts, docs, "Qatar Airways")
    assert out.student_discount_percent == 10.0
    assert out.student_discount_source_domain == "qatarairways.com"


def test_verify_drops_uncorroborated_non_official():
    docs = [WebSnippet("A blog claims EgyptAir gives a 15% student discount", "https://randomblog.example/x")]
    facts = _AirlineFacts(
        student_discount_percent=15.0,
        student_discount_evidence="EgyptAir gives a 15% student discount",
        student_discount_support=[1],
        student_discount_confidence=0.9,
    )
    out = enrichment._verify(facts, docs, "EgyptAir")
    assert out.student_discount_percent is None


def test_verify_accepts_two_distinct_sources():
    docs = [
        WebSnippet("Site A: EgyptAir student fares are 12% off", "https://a.example/x"),
        WebSnippet("Site B: EgyptAir student discount of 12%", "https://b.example/y"),
    ]
    facts = _AirlineFacts(
        student_discount_percent=12.0,
        student_discount_evidence="EgyptAir student fares are 12% off",
        student_discount_support=[1, 2],
        student_discount_confidence=0.9,
    )
    out = enrichment._verify(facts, docs, "EgyptAir")
    assert out.student_discount_percent == 12.0


def test_verify_drops_low_confidence_even_when_official():
    docs = [WebSnippet("Student discount 10% first flight", "https://www.qatarairways.com/x")]
    facts = _AirlineFacts(
        student_discount_percent=10.0,
        student_discount_evidence="Student discount 10% first flight",
        student_discount_support=[1],
        student_discount_confidence=0.3,
    )
    out = enrichment._verify(facts, docs, "Qatar Airways")
    assert out.student_discount_percent is None


