"""Core domain schemas for ParetoFly.

These types are the contract passed between LangGraph nodes:

``TripQuery`` (input) -> ``FlightOffer`` (raw search) -> ``ScoredFlight``
(after scoring) -> ``Recommendation`` (final, with narrative).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"

    @property
    def serpapi_code(self) -> int:
        """Map to SerpAPI ``travel_class`` codes (1-4)."""

        return {
            CabinClass.ECONOMY: 1,
            CabinClass.PREMIUM_ECONOMY: 2,
            CabinClass.BUSINESS: 3,
            CabinClass.FIRST: 4,
        }[self]


class Weights(BaseModel):
    """User-tunable trade-off weights. Persona defaults live in the scoring module."""

    price: float = 0.28
    duration: float = 0.14
    stops: float = 0.10
    layover_quality: float = 0.09
    arrival_fit: float = 0.14
    reliability: float = 0.09
    aircraft_match: float = 0.04
    carbon: float = 0.04
    luggage_fit: float = 0.08


class ParsedSignals(BaseModel):
    """Structured signals extracted from the free-text intake box by the LLM."""

    checked_bags: int = 0
    carry_on_only: bool = False
    avoid_red_eye: bool = False
    travel_with_child: bool = False
    travel_with_infant: bool = False
    mobility_needs: bool = False
    motion_sickness: bool = False
    is_student: bool = False
    max_cabin_baggage_kg: Optional[float] = None  # traveler's stated cabin-bag need
    preferred_arrival_start_hour: Optional[int] = None  # local hour 0-23
    preferred_arrival_end_hour: Optional[int] = None
    preferred_aircraft: list[str] = Field(default_factory=list)
    avoided_aircraft: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TripQuery(BaseModel):
    """Validated trip request assembled from the hybrid intake form + free text."""

    origin: str = Field(..., description="IATA code or city/airport name")
    destination: str = Field(..., description="IATA code or city/airport name")
    depart_date: date
    return_date: Optional[date] = None

    adults: int = Field(default=1, ge=1)
    children: int = Field(default=0, ge=0)
    infants: int = Field(default=0, ge=0)
    cabin: CabinClass = CabinClass.ECONOMY

    # Optional "Refine" panel fields
    max_stops: Optional[int] = Field(default=None, ge=0)
    budget: Optional[float] = Field(default=None, gt=0)
    max_layover_minutes: Optional[int] = Field(default=None, gt=0)
    preferred_airlines: list[str] = Field(default_factory=list)
    excluded_airlines: list[str] = Field(default_factory=list)
    is_student: bool = False
    eco_friendly: bool = Field(
        default=False,
        description="When true, carbon emissions become a real ranking factor; otherwise they are ignored.",
    )
    currency: str = "USD"

    # Free-text box + parsed result
    free_text: Optional[str] = None
    signals: ParsedSignals = Field(default_factory=ParsedSignals)

    weights: Weights = Field(default_factory=Weights)
    persona: Optional[str] = Field(
        default=None,
        description="Persona preset driving default weights: 'student', 'business', or 'family'.",
    )

    @field_validator("origin", "destination")
    @classmethod
    def _resolve_airport(cls, v: str) -> str:
        from app.airports import resolve_airport

        return resolve_airport(v)

    @property
    def is_round_trip(self) -> bool:
        return self.return_date is not None

    @property
    def total_passengers(self) -> int:
        return self.adults + self.children + self.infants


class FlightSegment(BaseModel):
    """A single flight leg."""

    departure_airport: str
    departure_time: datetime
    arrival_airport: str
    arrival_time: datetime
    airline: str
    flight_number: str
    aircraft: Optional[str] = None
    cabin: Optional[str] = None
    duration_minutes: int
    legroom: Optional[str] = None
    often_delayed: bool = False
    extensions: list[str] = Field(default_factory=list)


class Layover(BaseModel):
    airport: str
    duration_minutes: int
    overnight: bool = False


class FlightOffer(BaseModel):
    """A bookable itinerary returned by the search source (normalized)."""

    id: str
    segments: list[FlightSegment]
    layovers: list[Layover] = Field(default_factory=list)
    total_duration_minutes: int
    price: float
    currency: str = "USD"
    carbon_emissions_g: Optional[int] = None
    trip_type: Optional[str] = None
    airline_logo: Optional[str] = None
    booking_token: Optional[str] = None
    source: str = "serpapi_google_flights"
    extensions: list[str] = Field(default_factory=list)

    # Populated during enrichment / normalization
    true_price: Optional[float] = None
    student_discount_amount: Optional[float] = None
    student_discount_percent: Optional[float] = None
    student_discount_conditional: bool = False
    student_discount_source: Optional[str] = None
    student_discount_source_url: Optional[str] = None
    student_discount_evidence: Optional[str] = None
    site_discount_amount: Optional[float] = None
    site_discount_source: Optional[str] = None
    site_discount_source_url: Optional[str] = None
    site_discount_evidence: Optional[str] = None
    baggage_allowance_pieces: Optional[int] = None
    baggage_allowance_kg: Optional[float] = None
    student_baggage_bonus_pieces: Optional[int] = None
    student_baggage_bonus_kg: Optional[float] = None
    price_breakdown: dict[str, float] = Field(default_factory=dict)

    @property
    def stops(self) -> int:
        return max(len(self.segments) - 1, 0)

    @property
    def airlines(self) -> list[str]:
        return sorted({s.airline for s in self.segments})

    @property
    def departure_time(self) -> datetime:
        return self.segments[0].departure_time

    @property
    def arrival_time(self) -> datetime:
        return self.segments[-1].arrival_time

    @property
    def effective_price(self) -> float:
        return self.true_price if self.true_price is not None else self.price

    @property
    def total_cabin_baggage_kg(self) -> Optional[float]:
        """Base cabin allowance plus any student bonus (None if unknown)."""

        base, bonus = self.baggage_allowance_kg, self.student_baggage_bonus_kg
        if base is None and bonus is None:
            return None
        return (base or 0.0) + (bonus or 0.0)

    @property
    def total_cabin_baggage_pieces(self) -> Optional[int]:
        """Base cabin pieces plus any student bonus (None if unknown)."""

        base, bonus = self.baggage_allowance_pieces, self.student_baggage_bonus_pieces
        if base is None and bonus is None:
            return None
        return (base or 0) + (bonus or 0)


class ScoredFlight(BaseModel):
    """A flight offer with its per-feature and aggregate scores."""

    offer: FlightOffer
    feature_scores: dict[str, float] = Field(default_factory=dict)
    total_score: float = 0.0

    @property
    def top_features(self) -> list[str]:
        """Feature names sorted by descending contribution."""

        return [name for name, _ in sorted(
            self.feature_scores.items(), key=lambda kv: kv[1], reverse=True
        )]


class Recommendation(BaseModel):
    """Final ranked recommendation with plain-English reasoning."""

    rank: int
    scored: ScoredFlight
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    narrative: Optional[str] = None
