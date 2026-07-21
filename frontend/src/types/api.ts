// TypeScript mirrors of the backend Pydantic schemas (app/models/schemas.py).

export type CabinClass = "economy" | "premium_economy" | "business" | "first";

export type Persona = "student" | "business" | "family";

export interface Weights {
  price: number;
  duration: number;
  stops: number;
  layover_quality: number;
  arrival_fit: number;
  reliability: number;
  aircraft_match: number;
  carbon: number;
}

export interface ParsedSignals {
  checked_bags: number;
  carry_on_only: boolean;
  avoid_red_eye: boolean;
  travel_with_child: boolean;
  travel_with_infant: boolean;
  mobility_needs: boolean;
  motion_sickness: boolean;
  preferred_arrival_start_hour: number | null;
  preferred_arrival_end_hour: number | null;
  preferred_aircraft: string[];
  avoided_aircraft: string[];
  notes: string[];
}

/** Request body for POST /search and /search/stream. */
export interface TripQuery {
  origin: string;
  destination: string;
  depart_date: string; // ISO date (YYYY-MM-DD)
  return_date?: string | null;
  adults: number;
  children: number;
  infants: number;
  cabin: CabinClass;
  max_stops?: number | null;
  budget?: number | null;
  max_layover_minutes?: number | null;
  preferred_airlines?: string[];
  excluded_airlines?: string[];
  currency: string;
  free_text?: string | null;
  persona?: Persona | null;
}

export interface FlightSegment {
  departure_airport: string;
  departure_time: string;
  arrival_airport: string;
  arrival_time: string;
  airline: string;
  flight_number: string;
  aircraft?: string | null;
  cabin?: string | null;
  duration_minutes: number;
  legroom?: string | null;
  often_delayed: boolean;
  extensions: string[];
}

export interface Layover {
  airport: string;
  duration_minutes: number;
  overnight: boolean;
}

export interface FlightOffer {
  id: string;
  segments: FlightSegment[];
  layovers: Layover[];
  total_duration_minutes: number;
  price: number;
  currency: string;
  carbon_emissions_g?: number | null;
  trip_type?: string | null;
  airline_logo?: string | null;
  booking_token?: string | null;
  source: string;
  extensions: string[];
  true_price?: number | null;
}

export type FeatureName =
  | "price"
  | "duration"
  | "stops"
  | "layover_quality"
  | "arrival_fit"
  | "reliability"
  | "aircraft_match"
  | "carbon";

export interface ScoredFlight {
  offer: FlightOffer;
  feature_scores: Record<FeatureName, number>;
  total_score: number;
}

export interface Recommendation {
  rank: number;
  scored: ScoredFlight;
  pros: string[];
  cons: string[];
  narrative?: string | null;
}

/** Response body from POST /search (and the terminal `result` SSE event). */
export interface SearchResult {
  error: string | null;
  log: string[];
  recommendations: Recommendation[];
}

/** Payload of each `progress` SSE event. */
export interface ProgressEvent {
  node: string;
  message: string;
}
