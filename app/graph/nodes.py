"""LangGraph node functions for the ParetoFly agent.

Phase 4 wires a deterministic path: ``intake -> search -> score -> rank ->
explain -> present``. The ``explain`` node uses rule-based pros/cons here; an
LLM-backed narrative is layered on in a later phase.
"""

from __future__ import annotations

from app.graph.state import GraphState
from app.enrichment import enrich_true_prices
from app.llm.explain import write_explanations
from app.llm.intake import parse_free_text
from app.models.schemas import Recommendation, ScoredFlight, TripQuery
from app.scoring import diversity_top_k, infer_persona, score_offers
from app.tools import SerpApiError, search_flights


def _log(state: GraphState, message: str) -> list[str]:
    return [*state.get("log", []), message]


def intake_node(state: GraphState) -> GraphState:
    """Validate the query and parse the free-text box into structured signals."""

    query: TripQuery = state["query"]
    query.signals = parse_free_text(query)
    # Auto-select a persona (drives default weights) unless the caller set one.
    if query.persona is None:
        query.persona = infer_persona(query)
    persona_note = f" [persona={query.persona}]" if query.persona else ""
    return {
        "query": query,
        "log": _log(state, f"intake: {query.origin}->{query.destination} on {query.depart_date}{persona_note}"),
    }


def search_node(state: GraphState) -> GraphState:
    """Fetch raw offers from the flight source."""

    query: TripQuery = state["query"]
    try:
        offers = search_flights(query)
    except SerpApiError as exc:
        return {"error": str(exc), "log": _log(state, f"search: FAILED ({exc})")}
    return {"offers": offers, "log": _log(state, f"search: {len(offers)} offers")}


def score_node(state: GraphState) -> GraphState:
    """Apply the multi-criteria scoring model."""

    offers = state.get("offers", [])
    if not offers:
        return {"scored": [], "log": _log(state, "score: no offers to score")}
    scored = score_offers(offers, state["query"])
    return {"scored": scored, "log": _log(state, f"score: scored {len(scored)} offers")}


def enrich_node(state: GraphState) -> GraphState:
    """Fold checked-baggage fees into true prices (skipped when no checked bags)."""

    offers = state.get("offers", [])
    adjusted = enrich_true_prices(offers, state["query"])
    return {"offers": offers, "log": _log(state, f"enrich: adjusted {adjusted} true prices")}


def rank_node(state: GraphState) -> GraphState:
    """Pick a diverse top-3."""

    scored = state.get("scored", [])
    top = diversity_top_k(scored, k=3)
    recs = [Recommendation(rank=i + 1, scored=s) for i, s in enumerate(top)]
    return {"recommendations": recs, "log": _log(state, f"rank: selected top {len(recs)}")}


def _fmt_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h{m:02d}m"


def _rule_based_reasons(rec: Recommendation, all_recs: list[Recommendation]) -> tuple[list[str], list[str]]:
    offer = rec.scored.offer
    prices = [r.scored.offer.effective_price for r in all_recs]
    durations = [r.scored.offer.total_duration_minutes for r in all_recs]
    pros: list[str] = []
    cons: list[str] = []

    if offer.effective_price == min(prices):
        pros.append(f"Cheapest of the three at {offer.currency} {offer.effective_price:.0f}")
    elif offer.effective_price == max(prices) and len(set(prices)) > 1:
        cons.append(f"Priciest option at {offer.currency} {offer.effective_price:.0f}")

    if offer.stops == 0:
        pros.append("Nonstop")
    elif offer.stops >= 2:
        cons.append(f"{offer.stops} stops")

    if offer.total_duration_minutes == min(durations):
        pros.append(f"Shortest total travel time ({_fmt_duration(offer.total_duration_minutes)})")

    overnight = any(l.overnight for l in offer.layovers)
    if overnight:
        cons.append("Includes an overnight layover")
    long_layover = any(l.duration_minutes > 300 and not l.overnight for l in offer.layovers)
    if long_layover:
        cons.append("Long layover (5h+)")
    tight = any(l.duration_minutes < 60 for l in offer.layovers)
    if tight:
        cons.append("Tight connection (under 1h)")

    arr = offer.arrival_time
    if 0 <= arr.hour < 5:
        cons.append(f"Red-eye arrival at {arr.strftime('%H:%M')}")
    if rec.scored.feature_scores.get("arrival_fit", 0) >= 0.13:
        pros.append(f"Arrives {arr.strftime('%H:%M')}, matching your preferred window")

    if any(s.often_delayed for s in offer.segments):
        cons.append("One leg is often delayed 30+ min")

    if offer.carbon_emissions_g is not None:
        carbons = [r.scored.offer.carbon_emissions_g or 0 for r in all_recs]
        if offer.carbon_emissions_g == min(c for c in carbons if c):
            pros.append("Lowest carbon emissions of the three")

    if not pros:
        pros.append("Balanced across price, time, and convenience")
    return pros, cons


def explain_node(state: GraphState) -> GraphState:
    """Attach reasoning to each recommendation.

    Rule-based pros/cons + narrative are always computed as a grounded baseline;
    the LLM then rewrites them into richer prose when available (falling back to
    the rule-based version on any failure).
    """

    recs = state.get("recommendations", [])
    for rec in recs:
        pros, cons = _rule_based_reasons(rec, recs)
        rec.pros = pros
        rec.cons = cons
        offer = rec.scored.offer
        route = " -> ".join(
            [offer.segments[0].departure_airport] + [s.arrival_airport for s in offer.segments]
        )
        rec.narrative = (
            f"{', '.join(offer.airlines)} | {route} | "
            f"{offer.currency} {offer.effective_price:.0f}, {_fmt_duration(offer.total_duration_minutes)}, "
            f"{offer.stops} stop(s)."
        )

    used_llm = write_explanations(recs, state["query"])
    how = "LLM" if used_llm else "rule-based"
    return {"recommendations": recs, "log": _log(state, f"explain: attached reasons ({how})")}


def present_node(state: GraphState) -> GraphState:
    """Terminal node (placeholder for streaming to a UI)."""

    return {"log": _log(state, "present: done")}
