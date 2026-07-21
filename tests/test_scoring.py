"""Unit tests for the scoring + ranking model."""

from __future__ import annotations

from datetime import date

import pytest

from app.models.schemas import ParsedSignals, TripQuery
from app.scoring.model import (
    PERSONA_WEIGHTS,
    _arrival_fit_score,
    _layover_score,
    _luggage_fit_score,
    _min_max_lower_better,
    _resolve_weights,
    _stops_score,
    diversity_top_k,
    infer_persona,
    score_offers,
)
from app.models.schemas import CabinClass, Weights
from tests.conftest import make_offers


def _family_query() -> TripQuery:
    return TripQuery(
        origin="DAC",
        destination="JFK",
        depart_date=date(2026, 8, 12),
        adults=1,
        children=1,
        signals=ParsedSignals(
            checked_bags=2,
            avoid_red_eye=True,
            travel_with_child=True,
            preferred_arrival_start_hour=12,
            preferred_arrival_end_hour=18,
        ),
    )


def test_min_max_lower_better_basic():
    assert _min_max_lower_better([10, 20, 30]) == [1.0, 0.5, 0.0]


def test_min_max_lower_better_all_equal():
    assert _min_max_lower_better([5, 5, 5]) == [1.0, 1.0, 1.0]


def test_stops_score_scale():
    offers = {o.id: o for o in make_offers()}
    assert _stops_score(offers["balanced"]) == 0.6  # 1 stop


def test_layover_overnight_penalized():
    offers = {o.id: o for o in make_offers()}
    assert _layover_score(offers["cheap"]) == pytest.approx(0.2)
    assert _layover_score(offers["balanced"]) == pytest.approx(1.0)


def test_arrival_fit_prefers_window():
    query = _family_query()
    offers = {o.id: o for o in make_offers()}
    # balanced arrives 14:15 (inside 12-18 window) -> high
    good = _arrival_fit_score(offers["balanced"], query)
    # cheap arrives 03:00 (red-eye) -> low
    bad = _arrival_fit_score(offers["cheap"], query)
    assert good > 0.8
    assert bad < 0.2


def test_score_offers_ranks_best_fit_first_for_family():
    query = _family_query()
    scored = score_offers(make_offers(), query)
    # The balanced (afternoon-arrival, wide-body, good layover) should top the
    # cheap red-eye/overnight/regional option for a family persona-ish query.
    assert scored[0].offer.id in {"balanced", "balanced_dupe"}
    assert scored[-1].offer.id == "cheap"


def test_diversity_top_k_removes_near_duplicate():
    query = _family_query()
    scored = score_offers(make_offers(), query)
    top3 = diversity_top_k(scored, k=3)
    ids = {s.offer.id for s in top3}
    # balanced and balanced_dupe are near-identical; only one should appear.
    assert not {"balanced", "balanced_dupe"}.issubset(ids)
    assert len(top3) == 3


def test_total_score_within_unit_range():
    query = _family_query()
    scored = score_offers(make_offers(), query)
    for s in scored:
        assert 0.0 <= s.total_score <= 1.0


def _base_query(**kwargs) -> TripQuery:
    params = dict(origin="DAC", destination="JFK", depart_date=date(2026, 8, 12))
    params.update(kwargs)
    return TripQuery(**params)


def test_infer_persona_family_from_children():
    assert infer_persona(_base_query(children=1)) == "family"


def test_infer_persona_family_from_signals():
    q = _base_query(signals=ParsedSignals(travel_with_infant=True))
    assert infer_persona(q) == "family"


def test_infer_persona_business_from_cabin():
    assert infer_persona(_base_query(cabin=CabinClass.BUSINESS)) == "business"


def test_infer_persona_business_from_tight_arrival_window():
    q = _base_query(
        signals=ParsedSignals(preferred_arrival_start_hour=8, preferred_arrival_end_hour=10)
    )
    assert infer_persona(q) == "business"


def test_infer_persona_student_from_budget():
    assert infer_persona(_base_query(budget=350)) == "student"


def test_infer_persona_none_when_ambiguous():
    assert infer_persona(_base_query()) is None


def test_resolve_weights_uses_inferred_persona():
    q = _base_query(children=1)
    assert _resolve_weights(q) == PERSONA_WEIGHTS["family"]


def test_resolve_weights_respects_explicit_persona():
    q = _base_query(persona="student")
    assert _resolve_weights(q) == PERSONA_WEIGHTS["student"]


def test_resolve_weights_custom_weights_override_persona():
    custom = Weights(price=0.9, duration=0.1, stops=0.0, layover_quality=0.0,
                     arrival_fit=0.0, reliability=0.0, aircraft_match=0.0, carbon=0.0)
    q = _base_query(children=1, weights=custom)
    assert _resolve_weights(q) == custom


def test_all_weight_presets_sum_to_one():
    fields = (
        "price", "duration", "stops", "layover_quality", "arrival_fit",
        "reliability", "aircraft_match", "carbon", "luggage_fit",
    )
    presets = {"default": Weights(), **PERSONA_WEIGHTS}
    for name, w in presets.items():
        total = sum(getattr(w, f) for f in fields)
        assert total == pytest.approx(1.0), f"{name} weights sum to {total}"


def test_layover_hard_limit_zeroes_feature():
    offers = {o.id: o for o in make_offers()}
    # balanced has a single 130-min layover.
    assert _layover_score(offers["balanced"], max_minutes=60) == 0.0
    assert _layover_score(offers["balanced"], max_minutes=240) == pytest.approx(1.0)


def test_luggage_fit_neutral_without_baggage_concern():
    query = _base_query()
    offers = make_offers()
    assert _luggage_fit_score(offers[0], query) == 0.5


def test_luggage_fit_rewards_sufficient_allowance():
    query = _base_query(signals=ParsedSignals(carry_on_only=True, max_cabin_baggage_kg=7.0))
    offers = make_offers()
    generous = offers[0]
    generous.baggage_allowance_kg = 10.0
    stingy = offers[1]
    stingy.baggage_allowance_kg = 3.0
    assert _luggage_fit_score(generous, query) == 1.0
    assert _luggage_fit_score(stingy, query) == pytest.approx(0.2)
