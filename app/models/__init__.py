"""Pydantic domain models for ParetoFly."""

from app.models.schemas import (
    CabinClass,
    FlightOffer,
    FlightSegment,
    Layover,
    ParsedSignals,
    Recommendation,
    ScoredFlight,
    TripQuery,
    Weights,
)

__all__ = [
    "CabinClass",
    "FlightOffer",
    "FlightSegment",
    "Layover",
    "ParsedSignals",
    "Recommendation",
    "ScoredFlight",
    "TripQuery",
    "Weights",
]
