"""LLM explain: generate grounded pros/cons + narrative for the top-3 (GPT-5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm.azure_client import get_full_llm
from app.models.schemas import Recommendation, TripQuery


class _FlightExplanation(BaseModel):
    rank: int
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    narrative: str = ""


class _ExplanationSet(BaseModel):
    items: list[_FlightExplanation] = Field(default_factory=list)


_SYSTEM = (
    "You are ParetoFly, a flight recommendation assistant. Given a traveler's "
    "constraints and three pre-scored flight options, write concise, honest "
    "pros/cons grounded ONLY in the provided facts. 2-4 pros and 0-3 cons each, "
    "as short phrases. Then a one-sentence narrative. Reference the traveler's "
    "specific needs (kids, bags, arrival time, red-eyes) when relevant. Do not "
    "invent prices, times, or amenities that are not given."
)


def _minutes(m: int) -> str:
    h, mm = divmod(m, 60)
    return f"{h}h{mm:02d}m"


def _offer_facts(rec: Recommendation) -> dict:
    o = rec.scored.offer
    return {
        "rank": rec.rank,
        "airlines": o.airlines,
        "route": [o.segments[0].departure_airport] + [s.arrival_airport for s in o.segments],
        "price": f"{o.currency} {o.effective_price:.0f}",
        "duration": _minutes(o.total_duration_minutes),
        "stops": o.stops,
        "departure": o.departure_time.strftime("%Y-%m-%d %H:%M"),
        "arrival": o.arrival_time.strftime("%Y-%m-%d %H:%M"),
        "layovers": [
            {"airport": l.airport, "minutes": l.duration_minutes, "overnight": l.overnight}
            for l in o.layovers
        ],
        "aircraft": [s.aircraft for s in o.segments],
        "often_delayed": any(s.often_delayed for s in o.segments),
        "carbon_g": o.carbon_emissions_g,
    }


def _traveler_context(query: TripQuery) -> dict:
    sig = query.signals
    return {
        "passengers": {"adults": query.adults, "children": query.children, "infants": query.infants},
        "cabin": query.cabin.value,
        "budget": query.budget,
        "checked_bags": sig.checked_bags,
        "avoid_red_eye": sig.avoid_red_eye,
        "preferred_arrival_window": [sig.preferred_arrival_start_hour, sig.preferred_arrival_end_hour],
        "travel_with_child": sig.travel_with_child,
        "motion_sickness": sig.motion_sickness,
        "notes": sig.notes,
    }


def write_explanations(recs: list[Recommendation], query: TripQuery) -> bool:
    """Populate ``pros``/``cons``/``narrative`` on each rec in place.

    Returns ``True`` if the LLM produced explanations, ``False`` on failure
    (caller should keep any existing rule-based reasons).
    """

    if not recs:
        return False

    payload = {
        "traveler": _traveler_context(query),
        "options": [_offer_facts(r) for r in recs],
    }
    prompt = (
        "Traveler and options (JSON):\n"
        f"{payload}\n\n"
        "Return an explanation for every option by rank."
    )
    try:
        llm = get_full_llm().with_structured_output(_ExplanationSet)
        result: _ExplanationSet = llm.invoke([("system", _SYSTEM), ("human", prompt)])
    except Exception:  # pragma: no cover - network/parse failure -> caller fallback
        return False

    by_rank = {item.rank: item for item in result.items}
    produced = False
    for rec in recs:
        item = by_rank.get(rec.rank)
        if not item:
            continue
        if item.pros:
            rec.pros = item.pros
        if item.cons:
            rec.cons = item.cons
        if item.narrative:
            rec.narrative = item.narrative
        produced = True
    return produced
