"""True-cost enrichment: add checked-baggage fees to the sticker price.

SerpAPI reports whether checked baggage costs extra ("Checked baggage for a
fee") but not the amount. When the traveler has checked bags we look the fee up
via Serper web search and let GPT-5-mini extract a number, then fold it into
``FlightOffer.true_price`` so the scorer ranks on real cost.

Gated on ``checked_bags > 0`` so default queries skip all network/LLM work.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field

from app.llm.azure_client import get_mini_llm
from app.models.schemas import FlightOffer, TripQuery
from app.tools.serper import SerperError, web_search

_DEFAULT_FEE_USD = 60.0  # conservative fallback when lookup fails


class _BaggageFee(BaseModel):
    amount: Optional[float] = Field(
        default=None, description="First checked-bag fee for one passenger, one way, in the given currency"
    )


def _fare_includes_checked_bag(offer: FlightOffer) -> bool:
    text = " ".join(offer.extensions).lower()
    if "for a fee" in text:
        return False
    return "checked baggage" in text or "checked bag" in text or "bag included" in text


@lru_cache(maxsize=64)
def _first_checked_bag_fee(airline: str, currency: str) -> float:
    """Estimate one airline's first checked-bag fee (cached per process)."""

    try:
        snippets = web_search(f"{airline} first checked baggage fee economy {currency}", num=5)
    except SerperError:
        return _DEFAULT_FEE_USD
    if not snippets:
        return _DEFAULT_FEE_USD

    prompt = (
        f"Airline: {airline}. Currency: {currency}.\n"
        "From these web snippets, extract the approximate fee for the FIRST "
        "checked bag for one economy passenger, one way. If unclear, return null.\n\n"
        + "\n".join(f"- {s}" for s in snippets)
    )
    try:
        llm = get_mini_llm().with_structured_output(_BaggageFee)
        result: _BaggageFee = llm.invoke(
            [("system", "You extract a single numeric baggage fee."), ("human", prompt)]
        )
    except Exception:  # pragma: no cover - safe fallback
        return _DEFAULT_FEE_USD

    if result.amount is None or result.amount < 0 or result.amount > 500:
        return _DEFAULT_FEE_USD
    return float(result.amount)


def enrich_true_prices(offers: list[FlightOffer], query: TripQuery) -> int:
    """Populate ``true_price`` on offers that charge for the traveler's bags.

    Returns the number of offers whose price was adjusted.
    """

    bags = query.signals.checked_bags
    if bags <= 0 or not offers:
        return 0

    paying_pax = max(query.adults + query.children, 1)
    adjusted = 0
    fee_cache: dict[str, float] = {}

    for offer in offers:
        if _fare_includes_checked_bag(offer):
            offer.true_price = offer.price
            continue
        airline = offer.segments[0].airline if offer.segments else "airline"
        if airline not in fee_cache:
            fee_cache[airline] = _first_checked_bag_fee(airline, query.currency)
        fee = fee_cache[airline]
        offer.true_price = offer.price + bags * paying_pax * fee
        adjusted += 1

    return adjusted
