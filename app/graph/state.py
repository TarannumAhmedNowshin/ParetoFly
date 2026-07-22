"""Shared LangGraph state for the ParetoFly agent."""

from __future__ import annotations

from typing import Optional, TypedDict

from app.models.schemas import FlightOffer, Recommendation, ScoredFlight, TripQuery


class GraphState(TypedDict, total=False):
    """State passed between nodes.

    ``total=False`` so nodes may return partial updates that LangGraph merges.
    """

    query: TripQuery
    offers: list[FlightOffer]
    scored: list[ScoredFlight]
    recommendations: list[Recommendation]
    log: list[str]
    error: Optional[str]
    session_id: Optional[str]
