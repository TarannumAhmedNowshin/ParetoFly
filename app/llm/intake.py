"""LLM intake: parse the free-text box into structured signals (GPT-5-mini)."""

from __future__ import annotations

from app.llm.azure_client import get_mini_llm
from app.logging_config import get_logger
from app.models.schemas import ParsedSignals, TripQuery

log = get_logger("llm.intake")

_SYSTEM = (
    "You extract structured travel constraints from a traveler's free-text note. "
    "Only set fields the text actually supports; leave the rest at their defaults. "
    "Arrival window hours are local 24h integers (0-23). "
    "For aircraft preferences use short model hints like '787', '777', 'A380', 'Embraer'. "
    "Interpret phrases: 'no red-eyes'/'no 3am arrivals' => avoid_red_eye; "
    "'X suitcases/checked bags' => checked_bags; 'carry-on only' => carry_on_only; "
    "'traveling with a child/kid/5-year-old' => travel_with_child; "
    "'infant/baby/lap child' => travel_with_infant; "
    "'wheelchair/mobility' => mobility_needs; 'airsick/motion sickness/nervous flyer' => motion_sickness; "
    "'student/university/college/scholar ID' => is_student; "
    "'X kg cabin/carry-on bag' => max_cabin_baggage_kg. "
    "Add any other useful hints as short strings in 'notes'."
)


def parse_free_text(query: TripQuery) -> ParsedSignals:
    """Return signals parsed from ``query.free_text`` merged with form-derived hints.

    Falls back to purely form-derived signals if there is no free text or the
    LLM call fails.
    """

    base = ParsedSignals(
        travel_with_child=query.children > 0,
        travel_with_infant=query.infants > 0,
        is_student=query.is_student,
    )

    if not query.free_text or not query.free_text.strip():
        log.debug("intake: no free text; using form-derived signals only")
        return base

    prompt = (
        f"Form context: {query.adults} adult(s), {query.children} child(ren), "
        f"{query.infants} infant(s), cabin={query.cabin.value}.\n"
        f"Traveler note: \"{query.free_text.strip()}\""
    )
    try:
        llm = get_mini_llm().with_structured_output(ParsedSignals)
        parsed: ParsedSignals = llm.invoke(
            [("system", _SYSTEM), ("human", prompt)]
        )
        log.info("intake: LLM parsed free text (%d chars)", len(query.free_text.strip()))
    except Exception as exc:  # pragma: no cover - network/parse failure -> safe fallback
        log.warning("intake: LLM parse failed (%s); using form-derived signals", exc)
        return base

    # Union form-derived flags with LLM output (form is authoritative for pax).
    parsed.travel_with_child = parsed.travel_with_child or base.travel_with_child
    parsed.travel_with_infant = parsed.travel_with_infant or base.travel_with_infant
    parsed.is_student = parsed.is_student or base.is_student
    return parsed
