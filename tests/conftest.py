"""Shared test fixtures: synthetic flight offers (no network)."""

from __future__ import annotations

from datetime import datetime

from app.models.schemas import FlightOffer, FlightSegment, Layover


def _seg(
    dep: str,
    arr: str,
    dep_time: str,
    arr_time: str,
    airline: str,
    number: str,
    aircraft: str = "Boeing 777",
    delayed: bool = False,
) -> FlightSegment:
    return FlightSegment(
        departure_airport=dep,
        departure_time=datetime.fromisoformat(dep_time),
        arrival_airport=arr,
        arrival_time=datetime.fromisoformat(arr_time),
        airline=airline,
        flight_number=number,
        aircraft=aircraft,
        duration_minutes=int(
            (datetime.fromisoformat(arr_time) - datetime.fromisoformat(dep_time)).total_seconds() // 60
        ),
        often_delayed=delayed,
    )


def make_offers() -> list[FlightOffer]:
    """A small, deterministic mix of nonstop and connecting itineraries."""

    # Cheapest but overnight layover, regional jet, red-eye arrival.
    cheap = FlightOffer(
        id="cheap",
        segments=[
            _seg("DAC", "DEL", "2026-08-12T02:00", "2026-08-12T05:00", "Air India", "AI1", "Airbus A320"),
            _seg("DEL", "JFK", "2026-08-12T20:00", "2026-08-13T03:00", "Air India", "AI2", "Embraer 190", delayed=True),
        ],
        layovers=[Layover(airport="DEL", duration_minutes=900, overnight=True)],
        total_duration_minutes=1500,
        price=760.0,
        carbon_emissions_g=700000,
    )

    # Best-fit: afternoon arrival, comfortable layover, wide-body.
    balanced = FlightOffer(
        id="balanced",
        segments=[
            _seg("DAC", "DOH", "2026-08-13T02:00", "2026-08-13T05:00", "Qatar Airways", "QR641"),
            _seg("DOH", "JFK", "2026-08-13T07:10", "2026-08-13T14:15", "Qatar Airways", "QR701"),
        ],
        layovers=[Layover(airport="DOH", duration_minutes=130)],
        total_duration_minutes=735,
        price=912.0,
        carbon_emissions_g=540000,
    )

    # Nonstop-ish, most convenient but pricey.
    convenient = FlightOffer(
        id="convenient",
        segments=[
            _seg("DAC", "IST", "2026-08-14T08:35", "2026-08-14T13:00", "Turkish", "TK713"),
            _seg("IST", "JFK", "2026-08-14T14:55", "2026-08-14T16:50", "Turkish", "TK1"),
        ],
        layovers=[Layover(airport="IST", duration_minutes=115)],
        total_duration_minutes=900,
        price=945.0,
        carbon_emissions_g=560000,
    )

    # A near-duplicate of `balanced` to exercise diversity filtering.
    balanced_dupe = FlightOffer(
        id="balanced_dupe",
        segments=[
            _seg("DAC", "DOH", "2026-08-13T03:00", "2026-08-13T06:00", "Qatar Airways", "QR643"),
            _seg("DOH", "JFK", "2026-08-13T08:10", "2026-08-13T15:15", "Qatar Airways", "QR703"),
        ],
        layovers=[Layover(airport="DOH", duration_minutes=130)],
        total_duration_minutes=735,
        price=915.0,
        carbon_emissions_g=545000,
    )

    return [cheap, balanced, convenient, balanced_dupe]
