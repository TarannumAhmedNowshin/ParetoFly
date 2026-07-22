"""Downloadable per-search report generation.

Renders the final recommendations for one search into a Markdown document and
persists it under the configured ``reports_dir`` as ``{session_id}_report.md``.
The API layer generates a ``session_id`` per search, calls
:func:`build_report_markdown` + :func:`save_report`, and exposes the file for
download via ``GET /report/{session_id}``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.logging_config import get_logger
from app.models.schemas import FlightOffer, Recommendation, TripQuery

_SESSION_ID_RE = re.compile(r"^[a-f0-9]{8,64}$")

log = get_logger("reporting")

# Human-friendly labels for the price-breakdown table rows.
_BREAKDOWN_LABELS = {
    "base": "Base fare",
    "baggage_fee": "Checked baggage fee",
    "student_discount": "Student discount",
    "site_discount": "Booking-site discount",
    "true_price": "You pay",
}


def is_valid_session_id(session_id: str) -> bool:
    """Return ``True`` for a safe hex session id (guards against path traversal)."""

    return bool(_SESSION_ID_RE.match(session_id))


def reports_dir() -> Path:
    """Resolve the configured reports directory, creating it if needed."""

    path = Path(get_settings().reports_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_path(session_id: str) -> Path:
    """Return the on-disk path for a session's report (validated)."""

    if not is_valid_session_id(session_id):
        raise ValueError(f"Invalid session id: {session_id!r}")
    return reports_dir() / f"{session_id}_report.md"


def _fmt_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h{m:02d}m"


def _route(offer: FlightOffer) -> str:
    return " → ".join(
        [offer.segments[0].departure_airport] + [s.arrival_airport for s in offer.segments]
    )


def _summary_section(query: TripQuery) -> list[str]:
    sig = query.signals
    trip = "Round-trip" if query.is_round_trip else "One-way"
    lines = [
        "## Search summary",
        "",
        f"- **Route:** {query.origin} → {query.destination}",
        f"- **Dates:** {query.depart_date}"
        + (f" – {query.return_date}" if query.return_date else "")
        + f" ({trip})",
        f"- **Passengers:** {query.adults} adult(s), {query.children} child(ren), {query.infants} infant(s)",
        f"- **Cabin:** {query.cabin.value}",
        f"- **Currency:** {query.currency}",
    ]
    if query.persona:
        lines.append(f"- **Persona:** {query.persona}")
    if query.budget:
        lines.append(f"- **Budget:** {query.currency} {query.budget:.0f}")
    if query.max_stops is not None:
        lines.append(f"- **Max stops:** {query.max_stops}")
    if query.max_layover_minutes is not None:
        lines.append(f"- **Max layover:** {query.max_layover_minutes} min")

    prefs: list[str] = []
    if sig.is_student:
        prefs.append("student")
    if sig.checked_bags:
        prefs.append(f"{sig.checked_bags} checked bag(s)")
    if sig.carry_on_only:
        prefs.append("carry-on only")
    if sig.max_cabin_baggage_kg:
        prefs.append(f"{sig.max_cabin_baggage_kg:.0f}kg cabin bag")
    if sig.avoid_red_eye:
        prefs.append("no red-eyes")
    if sig.preferred_arrival_start_hour is not None and sig.preferred_arrival_end_hour is not None:
        prefs.append(
            f"arrive {sig.preferred_arrival_start_hour:02d}:00–{sig.preferred_arrival_end_hour:02d}:00"
        )
    if prefs:
        lines.append(f"- **Preferences:** {', '.join(prefs)}")
    if query.free_text:
        lines.append(f"- **Note:** {query.free_text.strip()}")
    lines.append("")
    return lines


def _breakdown_table(offer: FlightOffer) -> list[str]:
    if not offer.price_breakdown:
        return []
    lines = ["", "| Line item | Amount |", "| --- | ---: |"]
    for key, label in _BREAKDOWN_LABELS.items():
        if key in offer.price_breakdown:
            amount = offer.price_breakdown[key]
            lines.append(f"| {label} | {offer.currency} {amount:,.2f} |")
    lines.append("")
    return lines


def _baggage_lines(offer: FlightOffer) -> list[str]:
    """Report base cabin allowance, any student bonus, and the resulting total."""

    lines: list[str] = []
    base_kg = offer.baggage_allowance_kg
    bonus_kg = offer.student_baggage_bonus_kg
    total_kg = offer.total_cabin_baggage_kg
    if total_kg is not None:
        if bonus_kg:
            lines.append(
                f"- **Cabin baggage:** {(base_kg or 0):.0f}kg base + {bonus_kg:.0f}kg "
                f"student bonus = **{total_kg:.0f}kg total**"
            )
        else:
            lines.append(f"- **Cabin baggage:** {total_kg:.0f}kg")

    base_pc = offer.baggage_allowance_pieces
    bonus_pc = offer.student_baggage_bonus_pieces
    total_pc = offer.total_cabin_baggage_pieces
    if total_pc is not None:
        if bonus_pc:
            lines.append(
                f"- **Cabin pieces:** {(base_pc or 0)} base + {bonus_pc} student bonus = "
                f"**{total_pc} total**"
            )
        else:
            lines.append(f"- **Cabin pieces:** {total_pc}")
    return lines


def _shorten(text: str, limit: int = 140) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1].rstrip() + "\u2026"


def _provenance_lines(offer: FlightOffer) -> list[str]:
    """Show where each applied discount came from so users can judge reliability."""

    lines: list[str] = []
    if offer.student_discount_amount and (offer.student_discount_source or offer.student_discount_evidence):
        src = offer.student_discount_source or "web"
        quote = f" \u2014 \u201c{_shorten(offer.student_discount_evidence)}\u201d" if offer.student_discount_evidence else ""
        lines.append(f"- **Student discount source:** {src}{quote}")
    if offer.site_discount_amount and (
        offer.site_discount_source or offer.site_discount_source_url or offer.site_discount_evidence
    ):
        src = offer.site_discount_source or offer.site_discount_source_url or "web"
        quote = f" \u2014 \u201c{_shorten(offer.site_discount_evidence)}\u201d" if offer.site_discount_evidence else ""
        lines.append(f"- **Booking-site discount source:** {src}{quote}")
    return lines


def _recommendation_section(rec: Recommendation) -> list[str]:
    offer = rec.scored.offer
    lines = [
        f"### {rec.rank}. {', '.join(offer.airlines)} — {offer.currency} {offer.effective_price:.0f}",
        "",
        f"- **Route:** {_route(offer)}",
        f"- **Departs:** {offer.departure_time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Arrives:** {offer.arrival_time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Duration:** {_fmt_duration(offer.total_duration_minutes)} · **Stops:** {offer.stops}",
    ]
    if offer.student_discount_amount:
        pct = (
            f" (student −{offer.student_discount_percent:.0f}%)"
            if offer.student_discount_percent
            else " (student discount)"
        )
        cond = " — conditions apply" if offer.student_discount_conditional else ""
        lines.append(
            f"- **Fare:** ~~{offer.currency} {offer.price:.0f}~~ → "
            f"**{offer.currency} {offer.effective_price:.0f}**{pct}{cond}"
        )
    if offer.layovers:
        lay = "; ".join(
            f"{l.airport} {_fmt_duration(l.duration_minutes)}" + (" (overnight)" if l.overnight else "")
            for l in offer.layovers
        )
        lines.append(f"- **Layovers:** {lay}")
    lines += _baggage_lines(offer)
    lines += _provenance_lines(offer)
    lines.append(f"- **Score:** {rec.scored.total_score:.3f}")

    lines += _breakdown_table(offer)

    if rec.pros:
        lines.append("**Pros:**")
        lines += [f"- {p}" for p in rec.pros]
        lines.append("")
    if rec.cons:
        lines.append("**Cons:**")
        lines += [f"- {c}" for c in rec.cons]
        lines.append("")
    if rec.narrative:
        lines.append(f"> {rec.narrative}")
        lines.append("")
    return lines


def build_report_markdown(
    session_id: str,
    query: TripQuery,
    recommendations: list[Recommendation],
) -> str:
    """Render a full Markdown report for one search."""

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# ParetoFly flight report",
        "",
        f"**Session:** `{session_id}`  ",
        f"**Generated:** {generated}",
        "",
    ]
    lines += _summary_section(query)

    if not recommendations:
        lines += ["## Recommendations", "", "_No flights matched this search._", ""]
    else:
        lines += ["## Recommendations", ""]
        for rec in recommendations:
            lines += _recommendation_section(rec)

    lines += [
        "---",
        "",
        "_Discount and baggage figures are estimates gathered from public web "
        "sources at search time and may change. Confirm final pricing with the "
        "airline or booking site before purchase._",
        "",
    ]
    return "\n".join(lines)


def save_report(
    session_id: str,
    query: TripQuery,
    recommendations: list[Recommendation],
) -> Path:
    """Build and persist the report; returns the written file path."""

    markdown = build_report_markdown(session_id, query, recommendations)
    path = report_path(session_id)
    path.write_text(markdown, encoding="utf-8")
    log.info("report written: %s (%d recommendations)", path, len(recommendations))
    return path
