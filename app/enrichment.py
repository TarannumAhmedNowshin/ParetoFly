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
import contextvars
import re
from typing import Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm.azure_client import get_mini_llm
from app.logging_config import get_logger
from app.models.schemas import FlightOffer, TripQuery
from app.tools.kb_cache import KnowledgeCache, kb_key
from app.tools.web_knowledge import WebSnippet, get_web_documents

_DEFAULT_FEE_USD = 60.0  # conservative fallback when a baggage fee is unknown
_FACTS_VERSION = "airline_facts_v3"

log = get_logger("enrichment")


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
    student_discount_evidence: Optional[str] = Field(
        default=None, description="Exact sentence from the snippets that states the student fare discount"
    )
    site_discount_evidence: Optional[str] = Field(
        default=None, description="Exact sentence from the snippets that states the booking-site discount"
    )
    student_discount_support: list[int] = Field(
        default_factory=list,
        description="1-based indices of the numbered snippets that support the student discount",
    )
    student_discount_confidence: Optional[float] = Field(
        default=None, description="Confidence 0-1 that the student discount is real and current"
    )
    site_discount_support: list[int] = Field(
        default_factory=list,
        description="1-based indices of the numbered snippets that support the booking-site discount",
    )
    site_discount_confidence: Optional[float] = Field(
        default=None, description="Confidence 0-1 that the booking-site discount is real and current"
    )
    # Provenance filled in code from the supporting snippets (never from the LLM).
    student_discount_source_domain: Optional[str] = None
    student_discount_source_url: Optional[str] = None
    site_discount_source_domain: Optional[str] = None
    site_discount_source_url: Optional[str] = None
    cabin_baggage_kg: Optional[float] = Field(
        default=None, description="Included cabin/carry-on baggage weight allowance in kg"
    )
    cabin_baggage_pieces: Optional[int] = Field(
        default=None, description="Included cabin/carry-on baggage pieces"
    )


_EXTRACT_SYSTEM = (
    "You extract concrete, currently-advertised airline facts from numbered web "
    "snippets. Only fill a field when the snippets clearly support it; otherwise "
    "leave it null/false. For every discount you report: (a) copy the exact "
    "supporting sentence into the matching *_evidence field, (b) list the snippet "
    "numbers that support it in the matching *_support field, and (c) give a 0-1 "
    "*_confidence. Prefer facts stated on the airline's own official site. Use "
    "ONLY an airline's official student-program fare discount as "
    "student_discount_percent; for a tiered discount (e.g. 10%/15%/20%) return the "
    "lowest entry tier. Do NOT treat relative or comparative promotions (e.g. "
    "'save 50% vs airport check-in', 'up to X% off', 'cheaper than the counter') "
    "as a discount \u2014 leave those null. Set site_discount only for a named "
    "booking portal offering a concrete fare discount. Mark student_conditional "
    "true when the benefit requires joining a student club or identity verification."
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
    # Real carrier student-program discounts sit in the ~5-20% range; anything
    # higher is almost always a misread promo, so treat it as noise.
    f.student_discount_percent = ok(f.student_discount_percent, 0, 20)
    f.student_extra_baggage_kg = ok(f.student_extra_baggage_kg, 0, 40)
    f.student_extra_baggage_pieces = ok(f.student_extra_baggage_pieces, 0, 3)
    f.site_discount_amount = ok(f.site_discount_amount, 0, 1000)
    f.cabin_baggage_kg = ok(f.cabin_baggage_kg, 0, 40)
    f.cabin_baggage_pieces = ok(f.cabin_baggage_pieces, 0, 5)
    return f


# Comparative/promotional phrasing that must never be booked as a real discount
# (e.g. "save 50% vs airport check-in" is not an airfare reduction).
_PROMO_MARKERS = (
    " vs ", " vs.", "versus", "instead of", "compared to", "check-in",
    "check in", "airport counter", "as low as",
)


def _looks_promotional(text: Optional[str]) -> bool:
    return bool(text) and any(m in text.lower() for m in _PROMO_MARKERS)


def _drop_unsupported(f: _AirlineFacts) -> _AirlineFacts:
    """Discard monetary discounts that lack a concrete, non-promotional quote.

    A discount only survives if the model cited an exact supporting sentence and
    that sentence is not a relative/comparative promo. This is what stops made-up
    figures (e.g. a 25% student cut) and marketing lines from moving the price.
    """

    if f.student_discount_percent is not None or f.student_discount_amount is not None:
        if not f.student_discount_evidence or _looks_promotional(f.student_discount_evidence):
            log.debug("enrich: dropping unsupported student discount (evidence=%r)", f.student_discount_evidence)
            f.student_discount_percent = None
            f.student_discount_amount = None
    if f.site_discount_amount is not None:
        if not f.site_discount_evidence or _looks_promotional(f.site_discount_evidence):
            log.debug("enrich: dropping unsupported site discount (evidence=%r)", f.site_discount_evidence)
            f.site_discount_amount = None
            f.site_discount_source = None
    return f


def _airline_token(airline: str) -> str:
    return re.sub(r"[^a-z0-9]", "", airline.lower())


def _is_official_domain(domain: str, airline: str) -> bool:
    """True when ``domain`` looks like the airline's own site (e.g. qatarairways.com)."""

    token = _airline_token(airline)
    dom = re.sub(r"[^a-z0-9]", "", (domain or "").lower())
    return bool(token) and token in dom


def _support_docs(indices: list[int], docs: list[WebSnippet]) -> list[WebSnippet]:
    out: list[WebSnippet] = []
    for i in indices or []:
        if isinstance(i, int) and 1 <= i <= len(docs):
            out.append(docs[i - 1])
    return out


def _verify(facts: _AirlineFacts, docs: list[WebSnippet], airline: str) -> _AirlineFacts:
    """Gate discounts on source trust: official domain, corroboration, confidence.

    A discount is folded into the price only if the LLM was confident enough AND
    it is either vouched for by the airline's own official site or corroborated by
    at least ``enrich_min_corroboration`` distinct sources. The best supporting
    source (official first) is recorded as provenance for the report.
    """

    settings = get_settings()
    min_corr = settings.enrich_min_corroboration
    min_conf = settings.enrich_min_confidence
    trust_official = settings.enrich_trust_official_single

    def gate(has_value: bool, support: list[int], confidence: Optional[float]):
        if not has_value:
            return False, None
        if confidence is not None and confidence < min_conf:
            return False, None
        sup = _support_docs(support, docs)
        official = next((d for d in sup if _is_official_domain(d.domain, airline)), None)
        if official is not None and trust_official:
            return True, official
        distinct_domains = {d.domain for d in sup if d.domain}
        if len(distinct_domains) >= min_corr or len(sup) >= min_corr:
            return True, (sup[0] if sup else None)
        return False, None

    has_student = facts.student_discount_percent is not None or facts.student_discount_amount is not None
    accept, src = gate(has_student, facts.student_discount_support, facts.student_discount_confidence)
    if has_student and not accept:
        log.debug(
            "enrich: gating dropped student discount for %s (support=%s conf=%s)",
            airline, facts.student_discount_support, facts.student_discount_confidence,
        )
        facts.student_discount_percent = None
        facts.student_discount_amount = None
    elif accept and src is not None:
        facts.student_discount_source_domain = src.domain or None
        facts.student_discount_source_url = src.url or None

    has_site = facts.site_discount_amount is not None
    accept, src = gate(has_site, facts.site_discount_support, facts.site_discount_confidence)
    if has_site and not accept:
        log.debug(
            "enrich: gating dropped site discount for %s (support=%s conf=%s)",
            airline, facts.site_discount_support, facts.site_discount_confidence,
        )
        facts.site_discount_amount = None
        facts.site_discount_source = None
    elif accept and src is not None:
        facts.site_discount_source_domain = src.domain or None
        facts.site_discount_source_url = src.url or None

    return facts


def _fetch_airline_facts(airline: str, cabin: str, currency: str) -> tuple[_AirlineFacts, bool]:
    """Fetch + extract facts for one airline. Returns (facts, had_web_data)."""

    query = (
        f"{airline} {cabin} first checked baggage fee, student club discount and "
        f"extra baggage, cabin carry-on baggage allowance, exclusive booking discount {currency}"
    )
    docs = get_web_documents(query, num=8)
    if not docs:
        log.debug("enrich: no web snippets for %s (%s)", airline, cabin)
        return _AirlineFacts(), False

    numbered = "\n".join(f"[{i}] ({d.domain or 'unknown'}) {d.text}" for i, d in enumerate(docs, 1))
    prompt = (
        f"Airline: {airline}. Cabin: {cabin}. Currency: {currency}.\n"
        "Extract the airline's baggage fees, student benefits (fare discount + "
        "extra baggage), booking-site discount, and included cabin baggage "
        "allowance from these numbered snippets. Cite supporting snippet numbers "
        "and a confidence for each discount:\n\n" + numbered
    )
    try:
        llm = get_mini_llm().with_structured_output(_AirlineFacts)
        facts: _AirlineFacts = llm.invoke([("system", _EXTRACT_SYSTEM), ("human", prompt)])
    except Exception as exc:  # pragma: no cover - network/parse failure -> no data
        log.warning("enrich: fact extraction failed for %s (%s)", airline, exc)
        return _AirlineFacts(), False
    facts = _verify(_drop_unsupported(_clamp(facts)), docs, airline)
    log.debug("enrich: extracted facts for %s: %s", airline, facts.model_dump(exclude_none=True))
    return facts, True


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
        log.debug("enrich: skipped (offers=%d checked_bags=%d student=%s)", len(offers), bags, is_student)
        return 0

    settings = get_settings()
    cabin = query.cabin.value
    # Prices are in the currency the search actually returned (may differ from
    # query.currency when Google Flights fell back to USD); look fees up in that.
    currency = offers[0].currency if offers else query.currency
    airlines = {_airline_of(o) for o in offers}
    log.info(
        "enrich: start for %d offers, %d distinct airlines (bags=%d student=%s currency=%s)",
        len(offers), len(airlines), bags, is_student, currency,
    )

    # Fetch all distinct airlines concurrently (I/O-bound web + LLM calls).
    # A slow airline must not stall the whole search: bound the total wait and
    # fall back to empty facts for anything that didn't finish in time.
    # Copy the current context so worker threads keep the session-log binding.
    # Each task gets its OWN context copy: a single Context object cannot be
    # entered by more than one thread concurrently (raises "cannot enter
    # context: ... is already entered").
    facts_by_airline: dict[str, _AirlineFacts] = {}
    workers = max(1, min(settings.enrich_max_workers, len(airlines)))
    ex = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {
            ex.submit(contextvars.copy_context().run, _airline_facts, a, cabin, currency): a
            for a in airlines
        }
        try:
            for fut in as_completed(futures, timeout=settings.enrich_timeout):
                facts_by_airline[futures[fut]] = fut.result()
        except FuturesTimeout:
            log.warning(
                "enrich: timeout after %.0fs; %d/%d airlines resolved",
                settings.enrich_timeout, len(facts_by_airline), len(airlines),
            )
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
                offer.student_discount_evidence = facts.student_discount_evidence
                offer.student_discount_source = facts.student_discount_source_domain
                offer.student_discount_source_url = facts.student_discount_source_url
                breakdown["student_discount"] = -student_total
            offer.student_baggage_bonus_kg = facts.student_extra_baggage_kg
            offer.student_baggage_bonus_pieces = facts.student_extra_baggage_pieces

        site_total = 0.0
        if facts.site_discount_amount:
            site_total = facts.site_discount_amount * paying_pax
            offer.site_discount_amount = site_total
            offer.site_discount_source = facts.site_discount_source
            offer.site_discount_source_url = facts.site_discount_source_url
            offer.site_discount_evidence = facts.site_discount_evidence
            breakdown["site_discount"] = -site_total

        offer.baggage_allowance_pieces = facts.cabin_baggage_pieces
        offer.baggage_allowance_kg = facts.cabin_baggage_kg

        true_price = max(base + bag_fee_total - student_total - site_total, 0.0)
        offer.true_price = true_price
        breakdown["true_price"] = true_price
        offer.price_breakdown = breakdown

        if true_price != base:
            adjusted += 1

    log.info("enrich: done, adjusted %d/%d offer prices", adjusted, len(offers))
    return adjusted


