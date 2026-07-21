"""Command-line entry point for ParetoFly.

Phase 1: parse arguments into a validated ``TripQuery`` and echo it.
Later phases wire this into the LangGraph pipeline.

Example::

    python -m app.cli --from DAC --to JFK --depart 2026-08-12 \
        --adults 1 --children 1 --note "traveling with a 5 year old, no red-eyes"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

# Ensure non-ASCII narrative text (en/em dashes, etc.) renders on Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import get_settings
from app.models import CabinClass, TripQuery
from app.tools import SerpApiError, search_flights
from app.graph import run_pipeline


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - argparse surfaces the message
        raise argparse.ArgumentTypeError(f"Invalid date '{value}', expected YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paretofly",
        description="Find the top-3 Pareto-optimal flights with explanations.",
    )
    parser.add_argument("--from", dest="origin", required=True, help="Origin IATA code or city name, e.g. DAC or Dhaka")
    parser.add_argument("--to", dest="destination", required=True, help="Destination IATA code or city name, e.g. JFK or New York")
    parser.add_argument("--depart", dest="depart", required=True, type=_parse_date, help="Departure date YYYY-MM-DD")
    parser.add_argument("--return", dest="return_date", type=_parse_date, default=None, help="Return date YYYY-MM-DD (optional)")
    parser.add_argument("--adults", type=int, default=1)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--infants", type=int, default=0)
    parser.add_argument(
        "--cabin",
        type=CabinClass,
        choices=list(CabinClass),
        default=CabinClass.ECONOMY,
        help="Cabin class",
    )
    parser.add_argument("--max-stops", type=int, default=None)
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--max-layover", dest="max_layover", type=int, default=None, help="Max layover in minutes")
    parser.add_argument("--note", dest="free_text", default=None, help="Free-text 'anything else?' box")
    parser.add_argument("--currency", default=None)
    parser.add_argument("--search", action="store_true", help="Call SerpAPI and list raw offers")
    parser.add_argument("--run", action="store_true", help="Run the full agent pipeline and show top-3")
    return parser


def query_from_args(args: argparse.Namespace) -> TripQuery:
    settings = get_settings()
    return TripQuery(
        origin=args.origin,
        destination=args.destination,
        depart_date=args.depart,
        return_date=args.return_date,
        adults=args.adults,
        children=args.children,
        infants=args.infants,
        cabin=args.cabin,
        max_stops=args.max_stops,
        budget=args.budget,
        max_layover_minutes=args.max_layover,
        free_text=args.free_text,
        currency=args.currency or settings.default_currency,
    )


def _print_offers_summary(offers: list) -> None:
    print(f"\nSerpAPI returned {len(offers)} offers:")
    for offer in sorted(offers, key=lambda o: o.price)[:10]:
        route = " -> ".join(
            [offer.segments[0].departure_airport]
            + [s.arrival_airport for s in offer.segments]
        )
        h, m = divmod(offer.total_duration_minutes, 60)
        print(
            f"  {offer.currency} {offer.price:>7.0f} | {offer.stops} stop(s) | "
            f"{h}h{m:02d}m | {route} | {', '.join(offer.airlines)}"
        )


def _print_recommendations(state: dict) -> None:
    if state.get("error"):
        print(f"\n[error] {state['error']}")
        return
    recs = state.get("recommendations", [])
    medals = {1: "#1", 2: "#2", 3: "#3"}
    print(f"\nTop {len(recs)} recommendations:")
    for rec in recs:
        print(f"\n {medals.get(rec.rank, rec.rank)}  {rec.narrative}")
        for pro in rec.pros:
            print(f"     + {pro}")
        for con in rec.cons:
            print(f"     - {con}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    query = query_from_args(args)
    print("Parsed TripQuery:")
    print(query.model_dump_json(indent=2, exclude_none=True))

    if args.run:
        state = run_pipeline(query)
        _print_recommendations(state)
    elif args.search:
        try:
            offers = search_flights(query)
        except SerpApiError as exc:
            print(f"\n[error] {exc}")
            return 1
        _print_offers_summary(offers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
