"""Multi-criteria scoring model (PARETOFLY.md section 8).

Each candidate is scored on 8 sub-features normalized to ``[0, 1]`` (higher is
better), then combined with user/persona weights::

    score(f) = sum_i  w_i * norm(x_i(f))

The functions here are pure Python (no I/O, no LLM) so they are fully unit
testable and deterministic.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable

from app.models.schemas import FlightOffer, ScoredFlight, TripQuery, Weights, CabinClass

# Persona weight presets (used as defaults when a persona is detected).
PERSONA_WEIGHTS: dict[str, Weights] = {
    "student": Weights(price=0.42, duration=0.09, stops=0.07, layover_quality=0.06,
                       arrival_fit=0.09, reliability=0.09, aircraft_match=0.04, carbon=0.04,
                       luggage_fit=0.10),
    "business": Weights(price=0.13, duration=0.19, stops=0.14, layover_quality=0.09,
                        arrival_fit=0.19, reliability=0.14, aircraft_match=0.02, carbon=0.03,
                        luggage_fit=0.07),
    "family": Weights(price=0.23, duration=0.18, stops=0.11, layover_quality=0.09,
                      arrival_fit=0.17, reliability=0.07, aircraft_match=0.04, carbon=0.03,
                      luggage_fit=0.08),
}

_STUDENT_BUDGET_THRESHOLD = 500.0


def infer_persona(query: TripQuery) -> str | None:
    """Best-effort persona guess from the query/signals.

    Priority: family (kids) > business (premium cabin / tight arrival window) >
    student (tight budget). Returns ``None`` when nothing clearly applies so the
    neutral default weights are used.
    """

    signals = query.signals
    if query.children or query.infants or signals.travel_with_child or signals.travel_with_infant:
        return "family"

    if query.cabin in (CabinClass.BUSINESS, CabinClass.FIRST):
        return "business"
    start, end = signals.preferred_arrival_start_hour, signals.preferred_arrival_end_hour
    if start is not None and end is not None and 0 <= (end - start) <= 3:
        return "business"

    if query.budget is not None and query.budget < _STUDENT_BUDGET_THRESHOLD:
        return "student"

    return None

_REGIONAL_JET_HINTS = ("embraer", "crj", "e170", "e175", "e190", "regional", "atr", "dash 8")


def _min_max_lower_better(values: list[float]) -> list[float]:
    """Normalize so the lowest value maps to 1.0 and the highest to 0.0."""

    lo, hi = min(values), max(values)
    if math.isclose(hi, lo):
        return [1.0 for _ in values]
    span = hi - lo
    return [(hi - v) / span for v in values]


def _stops_score(offer: FlightOffer) -> float:
    return {0: 1.0, 1: 0.6, 2: 0.2}.get(offer.stops, 0.0)


def _layover_score(offer: FlightOffer, max_minutes: int | None = None) -> float:
    if not offer.layovers:
        return 1.0
    # Hard cap: any layover beyond the traveler's stated limit zeroes the feature.
    if max_minutes is not None and any(l.duration_minutes > max_minutes for l in offer.layovers):
        return 0.0
    per: list[float] = []
    for lay in offer.layovers:
        if lay.overnight:
            per.append(0.2)
            continue
        m = lay.duration_minutes
        if m < 45:
            per.append(0.2)
        elif m < 90:
            per.append(0.8)
        elif m <= 240:
            per.append(1.0)
        elif m <= 480:
            per.append(0.6)
        else:
            per.append(0.2)
    return sum(per) / len(per)


def _arrival_fit_score(offer: FlightOffer, query: TripQuery) -> float:
    sig = query.signals
    arrival_hour = offer.arrival_time.hour + offer.arrival_time.minute / 60.0

    # Red-eye penalty (arrivals 00:00-05:00) when the user asked to avoid them.
    red_eye = sig.avoid_red_eye and 0 <= arrival_hour < 5

    if sig.preferred_arrival_start_hour is None or sig.preferred_arrival_end_hour is None:
        base = 0.4 if red_eye else 0.5  # neutral when no window given
        return base

    start = sig.preferred_arrival_start_hour
    end = sig.preferred_arrival_end_hour
    center = (start + end) / 2.0
    # Gaussian: sigma scaled to half the window (min 1.5h) for tolerant falloff.
    sigma = max((end - start) / 2.0, 1.5)
    fit = math.exp(-((arrival_hour - center) ** 2) / (2 * sigma**2))
    if red_eye:
        fit *= 0.4
    return fit


def _reliability_score(offer: FlightOffer) -> float:
    if not offer.segments:
        return 0.5
    delayed = sum(1 for s in offer.segments if s.often_delayed)
    return 1.0 - delayed / len(offer.segments)


_CARRY_ON_BASELINE_KG = 7.0  # typical economy cabin-bag baseline


def _fare_has_checked_bag(offer: FlightOffer) -> bool:
    text = " ".join(offer.extensions).lower()
    if "for a fee" in text:
        return False
    return "checked baggage" in text or "checked bag" in text or "bag included" in text


def _luggage_fit_score(offer: FlightOffer, query: TripQuery) -> float:
    """Reward fares whose baggage allowance meets the traveler's stated need.

    Neutral (0.5) when the traveler expressed no baggage concern or when the
    airline's allowance could not be determined during enrichment.
    """

    sig = query.signals
    need_kg = sig.max_cabin_baggage_kg
    has_checked = sig.checked_bags > 0
    carry_focus = sig.carry_on_only or need_kg is not None
    if not (has_checked or carry_focus):
        return 0.5

    parts: list[float] = []
    if carry_focus:
        allow_kg = offer.total_cabin_baggage_kg
        if allow_kg is None:
            parts.append(0.5)
        else:
            need = need_kg if need_kg is not None else _CARRY_ON_BASELINE_KG
            if allow_kg >= need:
                parts.append(1.0)
            elif allow_kg >= 0.6 * need:
                parts.append(0.5)
            else:
                parts.append(0.2)
    if has_checked:
        parts.append(1.0 if _fare_has_checked_bag(offer) else 0.4)
    return sum(parts) / len(parts) if parts else 0.5


def _aircraft_match_score(offer: FlightOffer, query: TripQuery) -> float:
    sig = query.signals
    aircraft = [(s.aircraft or "").lower() for s in offer.segments]

    def _matches(patterns: Iterable[str]) -> bool:
        return any(p.lower() in a for a in aircraft for p in patterns if p)

    if sig.avoided_aircraft and _matches(sig.avoided_aircraft):
        return 0.0
    if sig.motion_sickness and _matches(_REGIONAL_JET_HINTS):
        return 0.2
    if sig.preferred_aircraft and _matches(sig.preferred_aircraft):
        return 1.0
    return 0.5


def _carbon_values(offers: list[FlightOffer]) -> list[float]:
    known = [o.carbon_emissions_g for o in offers if o.carbon_emissions_g is not None]
    fallback = max(known) if known else 0
    return [float(o.carbon_emissions_g if o.carbon_emissions_g is not None else fallback) for o in offers]


def _resolve_weights(query: TripQuery) -> Weights:
    # Explicitly customized weights always win.
    if query.weights != Weights():
        return query.weights
    # Otherwise fall back to the persona preset (explicit or inferred).
    persona = query.persona or infer_persona(query)
    if persona in PERSONA_WEIGHTS:
        return PERSONA_WEIGHTS[persona]
    return query.weights


def score_offers(offers: list[FlightOffer], query: TripQuery) -> list[ScoredFlight]:
    """Score and rank offers; returns a list sorted by descending total score."""

    if not offers:
        return []

    weights = _resolve_weights(query)

    price_norm = _min_max_lower_better([o.effective_price for o in offers])
    duration_norm = _min_max_lower_better([float(o.total_duration_minutes) for o in offers])
    carbon_norm = _min_max_lower_better(_carbon_values(offers))

    scored: list[ScoredFlight] = []
    for idx, offer in enumerate(offers):
        features = {
            "price": price_norm[idx],
            "duration": duration_norm[idx],
            "stops": _stops_score(offer),
            "layover_quality": _layover_score(offer, query.max_layover_minutes),
            "arrival_fit": _arrival_fit_score(offer, query),
            "reliability": _reliability_score(offer),
            "aircraft_match": _aircraft_match_score(offer, query),
            "carbon": carbon_norm[idx],
            "luggage_fit": _luggage_fit_score(offer, query),
        }
        weighted = {name: getattr(weights, name) * val for name, val in features.items()}
        total = sum(weighted.values())
        scored.append(
            ScoredFlight(offer=offer, feature_scores=weighted, total_score=total)
        )

    scored.sort(key=lambda s: s.total_score, reverse=True)
    return scored


def _too_similar(a: ScoredFlight, b: ScoredFlight) -> bool:
    same_airlines = a.offer.airlines == b.offer.airlines
    same_stops = a.offer.stops == b.offer.stops
    pa, pb = a.offer.effective_price, b.offer.effective_price
    close_price = abs(pa - pb) <= 0.05 * max(pa, pb, 1.0)
    return same_airlines and same_stops and close_price


def diversity_top_k(
    scored: list[ScoredFlight],
    k: int = 3,
    *,
    is_similar: Callable[[ScoredFlight, ScoredFlight], bool] = _too_similar,
) -> list[ScoredFlight]:
    """Greedily pick the top-k highest scorers while avoiding near-duplicates."""

    selected: list[ScoredFlight] = []
    for candidate in scored:  # already sorted best-first
        if any(is_similar(candidate, chosen) for chosen in selected):
            continue
        selected.append(candidate)
        if len(selected) == k:
            return selected

    # Backfill with the best remaining if diversity filtering left us short.
    if len(selected) < k:
        for candidate in scored:
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) == k:
                break
    return selected
