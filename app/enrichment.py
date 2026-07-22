"""True-cost enrichment: fold real-world fees and discounts into the price.

SerpAPI reports a sticker price but omits several things that change what a
traveler actually pays or gets: checked-baggage fees, student discounts,
booking-site discounts, and the included cabin-baggage allowance.

For each *distinct airline* we do a single web lookup (via the resilient
:mod:`app.tools.web_knowledge` provider chain) plus a single LLM extraction into
:class:`_AirlineFacts`, then fold the monetary items into
``FlightOffer.true_price`` so the scorer ranks on real cost. Lookups run
concurrently across airlines and are cached on disk (:class:`KnowledgeCache`) so
repeat airlines and repeat queries cost nothing.

Enrichment runs when the traveler has checked bags OR is a student (otherwise
default queries skip all I/O).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from typing import Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm.azure_client import get_mini_llm
from app.models.schemas import FlightOffer, TripQuery
from app.tools.kb_cache import KnowledgeCache, kb_key
from app.tools.web_knowledge import get_web_snippets

_DEFAULT_FEE_USD = 60.0  # conservative fallback when a baggage fee is unknown
_FACTS_VERSION = "airline_facts_v1"


class _AirlineFacts(BaseModel):
    """All enrichment facts for one airline+cabin+currency, from one lookup."""

    checked_bag_fee: Optional[float] = Field(
        default=None, description="First checked-bag fee for one economy passenger, one way"
    )
    student_discount_amount: Optional[float] = Field(
        default=None, description="Fixed student fare discount per passenger, one way"
    )
    student_discount_percent: Optional[float] = Field(
        default=None, description="Percentage student discount (entry/lowest tier if tiered)"
    )
    student_extra_baggage_kg: Optional[float] = Field(
        default=None, description="Extra baggage (kg) a student gets on top of the base allowance"
    )
    student_extra_baggage_pieces: Optional[int] = Field(
        default=None, description="Extra baggage pieces a student gets"
    )
    student_conditional: bool = Field(
        default=False, description="True if the student benefit needs membership/verification"
    )
    site_discount_amount: Optional[float] = Field(
        default=None, description="Booking-site exclusive discount per passenger, one way"
    )
    site_discount_source: Optional[str] = Field(
        default=None, description="Portal/source of the booking-site discount"
    )
    cabin_baggage_kg: Optional[float] = Field(
        default=None, description="Included cabin/carry-on baggage weight allowance in kg"
    )
    cabin_baggage_pieces: Optional[int] = Field(
        default=None, description="Included cabin/carry-on baggage pieces"
    )


_EXTRACT_SYSTEM = (
    "You extract concrete, currently-advertised airline facts from web snippets. "
    "Only fill a field when the snippets clearly support it; otherwise leave it "
    "null/false. For a tiered student discount (e.g. 10%/15%/20%) return the "
    "lowest entry tier as student_discount_percent. Mark student_conditional true "
    "when the benefit requires joining a student club or identity verification."
)

# In-process memo (L1). Only non-empty, freshly-fetched facts are stored so a
# transient search outage is retried on the next call rather than cached as "none".
_MEM: dict[tuple[str, str, str], _AirlineFacts] = {}
_CACHE: Optional[KnowledgeCache] = None


def _cache() -> KnowledgeCache:
    global _CACHE
    if _CACHE is None:
        s = get_settings()
        _CACHE = KnowledgeCache(s.kb_cache_dir, s.kb_cache_ttl_seconds)
    return _CACHE


def _fare_includes_checked_bag(offer: FlightOffer) -> bool:
    text = " ".join(offer.extensions).lower()
    if "for a fee" in text:
        return False
    return "checked baggage" in text or "checked bag" in text or "bag included" in text


def _clamp(f: _AirlineFacts) -> _AirlineFacts:
    def ok(v, lo, hi):
        return v if (v is not None and lo < v <= hi) else None

    f.checked_bag_fee = ok(f.checked_bag_fee, 0, 500)
    f.student_discount_amount = ok(f.student_discount_amount, 0, 1000)
    f.student_discount_percent = ok(f.student_discount_percent, 0, 60)
    f.student_extra_baggage_kg = ok(f.student_extra_baggage_kg, 0, 40)
    f.student_extra_baggage_pieces = ok(f.student_extra_baggage_pieces, 0, 3)
    f.site_discount_amount = ok(f.site_discount_amount, 0, 1000)
    f.cabin_baggage_kg = ok(f.cabin_baggage_kg, 0, 40)
    f.cabin_baggage_pieces = ok(f.cabin_baggage_pieces, 0, 5)
    return f


def _fetch_airline_facts(airline: str, cabin: str, currency: str) -> tuple[_AirlineFacts, bool]:
    """Fetch + extract facts for one airline. Returns (facts, had_web_data)."""

    query = (
        f"{airline} {cabin} first checked baggage fee, student club discount and "
        f"extra baggage, cabin carry-on baggage allowance, exclusive booking discount {currency}"
    )
    snippets = get_web_snippets(query, num=8)
    if not snippets:
        return _AirlineFacts(), False

    prompt = (
        f"Airline: {airline}. Cabin: {cabin}. Currency: {currency}.\n"
        "Extract the airline's baggage fees, student benefits (fare discount + "
        "extra baggage), booking-site discount, and included cabin baggage "
        "allowance from these snippets:\n\n" + "\n".join(f"- {s}" for s in snippets)
    )
    try:
        llm = get_mini_llm().with_structured_output(_AirlineFacts)
        facts: _AirlineFacts = llm.invoke([("system", _EXTRACT_SYSTEM), ("human", prompt)])
    except Exception:  # pragma: no cover - network/parse failure -> no data
        return _AirlineFacts(), False
    return _clamp(facts), True


def _airline_facts(airline: str, cabin: str, currency: str) -> _AirlineFacts:
    """Cached per (airline, cabin, currency): memory -> disk -> live fetch."""

    key_parts = (airline.lower(), cabin, currency)
    if key_parts in _MEM:
        return _MEM[key_parts]

    disk_key = kb_key(_FACTS_VERSION, *key_parts)
    cache = _cache()
    hit = cache.get(disk_key)
    if hit is not None:
        facts = _AirlineFacts.model_validate(hit)
        _MEM[key_parts] = facts
        return facts

    facts, had_data = _fetch_airline_facts(airline, cabin, currency)
    if had_data:
        cache.set(disk_key, facts.model_dump(mode="json"))
        _MEM[key_parts] = facts
    return facts


def _airline_of(offer: FlightOffer) -> str:
    return offer.segments[0].airline if offer.segments else "airline"


def enrich_true_prices(offers: list[FlightOffer], query: TripQuery) -> int:
    """Fold baggage fees and student/site discounts into ``true_price``.

    Looks up each distinct airline once (concurrently), records the cabin
    allowance used by the luggage-fit scorer, and returns the number of offers
    whose price was adjusted away from the sticker price.
    """

    sig = query.signals
    bags = sig.checked_bags
    is_student = sig.is_student
    if not offers or (bags <= 0 and not is_student):
        return 0

    settings = get_settings()
    cabin = query.cabin.value
    # Prices are in the currency the search actually returned (may differ from
    # query.currency when Google Flights fell back to USD); look fees up in that.
    currency = offers[0].currency if offers else query.currency
    airlines = {_airline_of(o) for o in offers}

    # Fetch all distinct airlines concurrently (I/O-bound web + LLM calls).
    # A slow airline must not stall the whole search: bound the total wait and
    # fall back to empty facts for anything that didn't finish in time.
    facts_by_airline: dict[str, _AirlineFacts] = {}
    workers = max(1, min(settings.enrich_max_workers, len(airlines)))
    ex = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {ex.submit(_airline_facts, a, cabin, currency): a for a in airlines}
        try:
            for fut in as_completed(futures, timeout=settings.enrich_timeout):
                facts_by_airline[futures[fut]] = fut.result()
        except FuturesTimeout:
            pass  # unfinished airlines -> empty facts (handled by .get default)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    paying_pax = max(query.adults + query.children, 1)
    adjusted = 0

    for offer in offers:
        facts = facts_by_airline.get(_airline_of(offer), _AirlineFacts())
        base = offer.price
        breakdown: dict[str, float] = {"base": base}

        bag_fee_total = 0.0
        if bags > 0 and not _fare_includes_checked_bag(offer):
            fee = facts.checked_bag_fee if facts.checked_bag_fee is not None else _DEFAULT_FEE_USD
            bag_fee_total = bags * paying_pax * fee
            breakdown["baggage_fee"] = bag_fee_total

        student_total = 0.0
        if is_student:
            if facts.student_discount_amount:
                student_total = facts.student_discount_amount * paying_pax
            elif facts.student_discount_percent:
                student_total = base * facts.student_discount_percent / 100.0
                offer.student_discount_percent = facts.student_discount_percent
            if student_total > 0:
                offer.student_discount_amount = student_total
                offer.student_discount_conditional = facts.student_conditional
                breakdown["student_discount"] = -student_total
            offer.student_baggage_bonus_kg = facts.student_extra_baggage_kg
            offer.student_baggage_bonus_pieces = facts.student_extra_baggage_pieces

        site_total = 0.0
        if facts.site_discount_amount:
            site_total = facts.site_discount_amount * paying_pax
            offer.site_discount_amount = site_total
            offer.site_discount_source = facts.site_discount_source
            breakdown["site_discount"] = -site_total

        offer.baggage_allowance_pieces = facts.cabin_baggage_pieces
        offer.baggage_allowance_kg = facts.cabin_baggage_kg

        true_price = max(base + bag_fee_total - student_total - site_total, 0.0)
        offer.true_price = true_price
        breakdown["true_price"] = true_price
        offer.price_breakdown = breakdown

        if true_price != base:
            adjusted += 1

    return adjusted


