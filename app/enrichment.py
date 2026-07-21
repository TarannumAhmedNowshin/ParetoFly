"""True-cost enrichment: fold real-world fees and discounts into the price.

SerpAPI reports a sticker price but omits several things that change what a
traveler actually pays or gets:

* **Checked-baggage fees** — only "Checked baggage for a fee" is flagged, not
  the amount.
* **Student discounts** — some airlines/portals discount fares for verified
  students.
* **Website / booking-site exclusive discounts** — promo pricing tied to a
  specific portal.
* **Cabin baggage allowance** — how much carry-on the fare actually includes.

We look these up via Serper web search + GPT-5-mini extraction and fold the
monetary items into ``FlightOffer.true_price`` so the scorer ranks on real cost.
Baggage allowance is stored for the luggage-fit scoring feature.

Every lookup is cached per (airline, cabin, currency) so repeated airlines and
repeat queries do no extra network/LLM work. Enrichment runs when the traveler
has checked bags OR is a student (otherwise default queries skip all I/O).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field

from app.llm.azure_client import get_mini_llm
from app.models.schemas import FlightOffer, TripQuery
from app.tools.serper import SerperError, web_search

_DEFAULT_FEE_USD = 60.0  # conservative fallback when a baggage lookup fails


class _BaggageFee(BaseModel):
    amount: Optional[float] = Field(
        default=None, description="First checked-bag fee for one passenger, one way, in the given currency"
    )


class _DiscountAmount(BaseModel):
    amount: Optional[float] = Field(
        default=None, description="Approximate discount for one passenger, one way, in the given currency"
    )
    source: Optional[str] = Field(
        default=None, description="Where the discount comes from (airline student portal, booking site name)"
    )


class _StudentBenefit(BaseModel):
    amount: Optional[float] = Field(
        default=None, description="Fixed student discount per passenger, one way, in the given currency"
    )
    percent: Optional[float] = Field(
        default=None, description="Percentage student discount off the fare (entry/minimum tier if tiered)"
    )
    extra_baggage_kg: Optional[float] = Field(
        default=None, description="Extra checked/cabin baggage allowance students get, in kg"
    )
    extra_baggage_pieces: Optional[int] = Field(
        default=None, description="Extra baggage pieces students get"
    )
    conditional: bool = Field(
        default=False,
        description="True if the benefit requires membership/verification (e.g. student club, SheerID)",
    )
    source: Optional[str] = Field(default=None, description="Program name, e.g. 'Student Club'")


class _BaggageAllowance(BaseModel):
    pieces: Optional[int] = Field(default=None, description="Included cabin/carry-on pieces")
    kg: Optional[float] = Field(default=None, description="Included cabin baggage weight allowance in kg")


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


@lru_cache(maxsize=64)
def _student_benefit(airline: str, cabin: str, currency: str) -> _StudentBenefit:
    """Look up a student program's fare discount and baggage perk (cached).

    Captures fixed-amount OR percentage discounts (many airline student clubs
    are percentage-based and tiered), plus any extra baggage allowance and
    whether the benefit is conditional on membership/verification. Returns an
    empty benefit when nothing concrete is found.
    """

    try:
        snippets = web_search(
            f"{airline} student club discount fare extra baggage allowance {cabin} {currency}", num=6
        )
    except SerperError:
        return _StudentBenefit()
    if not snippets:
        return _StudentBenefit()

    prompt = (
        f"Airline: {airline}. Cabin: {cabin}. Currency: {currency}.\n"
        "From these web snippets, extract the airline's STUDENT benefit, if any:\n"
        "- percent: the percentage a student saves on the fare. If tiered (e.g. "
        "10%/15%/20%), return the LOWEST/entry tier a first-time student gets.\n"
        "- amount: a fixed cash discount per passenger, if stated instead of a percent.\n"
        "- extra_baggage_kg / extra_baggage_pieces: additional baggage students get.\n"
        "- conditional: true if it requires joining a student club / verification.\n"
        "- source: the program name (e.g. 'Student Club').\n"
        "Only report concrete, currently-advertised airline student benefits. "
        "Leave any field null/false if not clearly stated.\n\n"
        + "\n".join(f"- {s}" for s in snippets)
    )
    try:
        llm = get_mini_llm().with_structured_output(_StudentBenefit)
        result: _StudentBenefit = llm.invoke(
            [("system", "You extract an airline student benefit."), ("human", prompt)]
        )
    except Exception:  # pragma: no cover - safe fallback
        return _StudentBenefit()

    # Sanity-clamp the extracted values; drop anything implausible.
    if result.amount is not None and not (0 < result.amount <= 1000):
        result.amount = None
    if result.percent is not None and not (0 < result.percent <= 60):
        result.percent = None
    if result.extra_baggage_kg is not None and not (0 < result.extra_baggage_kg <= 40):
        result.extra_baggage_kg = None
    if result.extra_baggage_pieces is not None and not (0 < result.extra_baggage_pieces <= 3):
        result.extra_baggage_pieces = None
    return result


@lru_cache(maxsize=64)
def _site_discount(airline: str, currency: str) -> tuple[float, Optional[str]]:
    """Estimate a booking-site exclusive discount and its source (0.0 when none)."""

    try:
        snippets = web_search(f"{airline} exclusive online booking discount promo code {currency}", num=5)
    except SerperError:
        return 0.0, None
    if not snippets:
        return 0.0, None

    prompt = (
        f"Airline: {airline}. Currency: {currency}.\n"
        "From these web snippets, extract any current WEBSITE / BOOKING-SITE "
        "exclusive discount a traveler gets by booking on a specific portal, per "
        "ticket, one way, in the given currency, plus the portal/source name. "
        "Only report a concrete, currently-advertised discount. If none, return null.\n\n"
        + "\n".join(f"- {s}" for s in snippets)
    )
    try:
        llm = get_mini_llm().with_structured_output(_DiscountAmount)
        result: _DiscountAmount = llm.invoke(
            [("system", "You extract a single numeric booking-site discount."), ("human", prompt)]
        )
    except Exception:  # pragma: no cover - safe fallback
        return 0.0, None

    if result.amount is None or result.amount <= 0 or result.amount > 1000:
        return 0.0, None
    return float(result.amount), result.source


@lru_cache(maxsize=64)
def _baggage_allowance(airline: str, cabin: str) -> tuple[Optional[int], Optional[float]]:
    """Estimate the included cabin-baggage allowance (pieces, kg)."""

    try:
        snippets = web_search(f"{airline} {cabin} cabin carry-on baggage allowance pieces kg", num=5)
    except SerperError:
        return None, None
    if not snippets:
        return None, None

    prompt = (
        f"Airline: {airline}. Cabin: {cabin}.\n"
        "From these web snippets, extract the included CABIN / carry-on baggage "
        "allowance: number of pieces and total weight in kg. Return null for a "
        "field that is unclear.\n\n"
        + "\n".join(f"- {s}" for s in snippets)
    )
    try:
        llm = get_mini_llm().with_structured_output(_BaggageAllowance)
        result: _BaggageAllowance = llm.invoke(
            [("system", "You extract a cabin baggage allowance."), ("human", prompt)]
        )
    except Exception:  # pragma: no cover - safe fallback
        return None, None

    pieces = result.pieces if result.pieces and 0 < result.pieces <= 5 else None
    kg = result.kg if result.kg and 0 < result.kg <= 40 else None
    return pieces, kg


def enrich_true_prices(offers: list[FlightOffer], query: TripQuery) -> int:
    """Fold baggage fees and student/site discounts into ``true_price``.

    Also records the cabin-baggage allowance used by the luggage-fit scorer.
    Runs only when the traveler has checked bags or is a student. Returns the
    number of offers whose price was adjusted away from the sticker price.
    """

    sig = query.signals
    bags = sig.checked_bags
    is_student = sig.is_student
    if not offers or (bags <= 0 and not is_student):
        return 0

    paying_pax = max(query.adults + query.children, 1)
    cabin = query.cabin.value
    adjusted = 0

    for offer in offers:
        airline = offer.segments[0].airline if offer.segments else "airline"

        base = offer.price
        breakdown: dict[str, float] = {"base": base}

        bag_fee_total = 0.0
        if bags > 0 and not _fare_includes_checked_bag(offer):
            fee = _first_checked_bag_fee(airline, query.currency)
            bag_fee_total = bags * paying_pax * fee
            breakdown["baggage_fee"] = bag_fee_total

        student_total = 0.0
        if is_student:
            benefit = _student_benefit(airline, cabin, query.currency)
            if benefit.amount:
                # Fixed cash discount is per paying passenger.
                student_total = benefit.amount * paying_pax
            elif benefit.percent:
                # Percentage applies to the whole fare (already covers all pax).
                student_total = base * benefit.percent / 100.0
                offer.student_discount_percent = benefit.percent
            if student_total > 0:
                offer.student_discount_amount = student_total
                offer.student_discount_conditional = benefit.conditional
                breakdown["student_discount"] = -student_total
            # Student baggage perk (independent of the fare discount).
            offer.student_baggage_bonus_kg = benefit.extra_baggage_kg
            offer.student_baggage_bonus_pieces = benefit.extra_baggage_pieces

        site_amount, site_source = _site_discount(airline, query.currency)
        site_total = 0.0
        if site_amount > 0:
            site_total = site_amount * paying_pax
            offer.site_discount_amount = site_total
            offer.site_discount_source = site_source
            breakdown["site_discount"] = -site_total

        # Record baggage allowance for the luggage-fit scoring feature.
        pieces, kg = _baggage_allowance(airline, cabin)
        offer.baggage_allowance_pieces = pieces
        offer.baggage_allowance_kg = kg

        true_price = max(base + bag_fee_total - student_total - site_total, 0.0)
        offer.true_price = true_price
        breakdown["true_price"] = true_price
        offer.price_breakdown = breakdown

        if true_price != base:
            adjusted += 1

    return adjusted

