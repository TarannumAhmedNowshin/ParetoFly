"""Airport resolution: accept a city/airport name or an IATA code, return IATA.

The frontend already submits clean 3-letter codes, but the API and CLI may
receive human input like "Dhaka" or "Hazrat Shahjalal". This module normalizes
either form to the IATA code that SerpAPI's ``departure_id``/``arrival_id`` need.

Any valid-looking 3-letter code is accepted as-is (SerpAPI supports codes beyond
this curated list); non-code input is matched against the table below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CODE_RE = re.compile(r"^[A-Za-z]{3}$")


@dataclass(frozen=True)
class Airport:
    code: str
    name: str
    city: str
    country: str


# Kept in sync with frontend/src/lib/airports.ts.
AIRPORTS: list[Airport] = [
    Airport("DAC", "Hazrat Shahjalal International", "Dhaka", "Bangladesh"),
    Airport("CGP", "Shah Amanat International", "Chattogram", "Bangladesh"),
    Airport("JFK", "John F. Kennedy International", "New York", "United States"),
    Airport("EWR", "Newark Liberty International", "Newark", "United States"),
    Airport("LGA", "LaGuardia", "New York", "United States"),
    Airport("LAX", "Los Angeles International", "Los Angeles", "United States"),
    Airport("SFO", "San Francisco International", "San Francisco", "United States"),
    Airport("ORD", "O'Hare International", "Chicago", "United States"),
    Airport("ATL", "Hartsfield-Jackson", "Atlanta", "United States"),
    Airport("DFW", "Dallas/Fort Worth International", "Dallas", "United States"),
    Airport("SEA", "Seattle-Tacoma International", "Seattle", "United States"),
    Airport("MIA", "Miami International", "Miami", "United States"),
    Airport("BOS", "Logan International", "Boston", "United States"),
    Airport("IAD", "Washington Dulles International", "Washington", "United States"),
    Airport("DEN", "Denver International", "Denver", "United States"),
    Airport("LAS", "Harry Reid International", "Las Vegas", "United States"),
    Airport("YYZ", "Toronto Pearson International", "Toronto", "Canada"),
    Airport("YVR", "Vancouver International", "Vancouver", "Canada"),
    Airport("LHR", "Heathrow", "London", "United Kingdom"),
    Airport("LGW", "Gatwick", "London", "United Kingdom"),
    Airport("MAN", "Manchester", "Manchester", "United Kingdom"),
    Airport("CDG", "Charles de Gaulle", "Paris", "France"),
    Airport("ORY", "Orly", "Paris", "France"),
    Airport("AMS", "Schiphol", "Amsterdam", "Netherlands"),
    Airport("FRA", "Frankfurt International", "Frankfurt", "Germany"),
    Airport("MUC", "Munich International", "Munich", "Germany"),
    Airport("MAD", "Adolfo Suarez Madrid-Barajas", "Madrid", "Spain"),
    Airport("BCN", "Barcelona-El Prat", "Barcelona", "Spain"),
    Airport("FCO", "Leonardo da Vinci-Fiumicino", "Rome", "Italy"),
    Airport("MXP", "Milan Malpensa", "Milan", "Italy"),
    Airport("ZRH", "Zurich", "Zurich", "Switzerland"),
    Airport("VIE", "Vienna International", "Vienna", "Austria"),
    Airport("CPH", "Copenhagen", "Copenhagen", "Denmark"),
    Airport("ARN", "Stockholm Arlanda", "Stockholm", "Sweden"),
    Airport("OSL", "Oslo Gardermoen", "Oslo", "Norway"),
    Airport("HEL", "Helsinki-Vantaa", "Helsinki", "Finland"),
    Airport("DUB", "Dublin", "Dublin", "Ireland"),
    Airport("LIS", "Humberto Delgado", "Lisbon", "Portugal"),
    Airport("IST", "Istanbul", "Istanbul", "Turkey"),
    Airport("SVO", "Sheremetyevo", "Moscow", "Russia"),
    Airport("DXB", "Dubai International", "Dubai", "United Arab Emirates"),
    Airport("AUH", "Abu Dhabi International", "Abu Dhabi", "United Arab Emirates"),
    Airport("DOH", "Hamad International", "Doha", "Qatar"),
    Airport("RUH", "King Khalid International", "Riyadh", "Saudi Arabia"),
    Airport("JED", "King Abdulaziz International", "Jeddah", "Saudi Arabia"),
    Airport("KWI", "Kuwait International", "Kuwait City", "Kuwait"),
    Airport("DEL", "Indira Gandhi International", "Delhi", "India"),
    Airport("BOM", "Chhatrapati Shivaji Maharaj", "Mumbai", "India"),
    Airport("BLR", "Kempegowda International", "Bengaluru", "India"),
    Airport("MAA", "Chennai International", "Chennai", "India"),
    Airport("CCU", "Netaji Subhas Chandra Bose", "Kolkata", "India"),
    Airport("HYD", "Rajiv Gandhi International", "Hyderabad", "India"),
    Airport("KTM", "Tribhuvan International", "Kathmandu", "Nepal"),
    Airport("CMB", "Bandaranaike International", "Colombo", "Sri Lanka"),
    Airport("KHI", "Jinnah International", "Karachi", "Pakistan"),
    Airport("LHE", "Allama Iqbal International", "Lahore", "Pakistan"),
    Airport("ISB", "Islamabad International", "Islamabad", "Pakistan"),
    Airport("BKK", "Suvarnabhumi", "Bangkok", "Thailand"),
    Airport("DMK", "Don Mueang International", "Bangkok", "Thailand"),
    Airport("SIN", "Changi", "Singapore", "Singapore"),
    Airport("KUL", "Kuala Lumpur International", "Kuala Lumpur", "Malaysia"),
    Airport("CGK", "Soekarno-Hatta International", "Jakarta", "Indonesia"),
    Airport("DPS", "Ngurah Rai International", "Bali", "Indonesia"),
    Airport("MNL", "Ninoy Aquino International", "Manila", "Philippines"),
    Airport("HAN", "Noi Bai International", "Hanoi", "Vietnam"),
    Airport("SGN", "Tan Son Nhat International", "Ho Chi Minh City", "Vietnam"),
    Airport("HKG", "Hong Kong International", "Hong Kong", "Hong Kong"),
    Airport("TPE", "Taoyuan International", "Taipei", "Taiwan"),
    Airport("ICN", "Incheon International", "Seoul", "South Korea"),
    Airport("NRT", "Narita International", "Tokyo", "Japan"),
    Airport("HND", "Haneda", "Tokyo", "Japan"),
    Airport("KIX", "Kansai International", "Osaka", "Japan"),
    Airport("PEK", "Beijing Capital International", "Beijing", "China"),
    Airport("PVG", "Shanghai Pudong International", "Shanghai", "China"),
    Airport("CAN", "Guangzhou Baiyun International", "Guangzhou", "China"),
    Airport("SYD", "Kingsford Smith", "Sydney", "Australia"),
    Airport("MEL", "Melbourne", "Melbourne", "Australia"),
    Airport("BNE", "Brisbane", "Brisbane", "Australia"),
    Airport("AKL", "Auckland", "Auckland", "New Zealand"),
    Airport("JNB", "O. R. Tambo International", "Johannesburg", "South Africa"),
    Airport("CPT", "Cape Town International", "Cape Town", "South Africa"),
    Airport("CAI", "Cairo International", "Cairo", "Egypt"),
    Airport("NBO", "Jomo Kenyatta International", "Nairobi", "Kenya"),
    Airport("ADD", "Bole International", "Addis Ababa", "Ethiopia"),
    Airport("LOS", "Murtala Muhammed International", "Lagos", "Nigeria"),
    Airport("GRU", "Sao Paulo/Guarulhos", "Sao Paulo", "Brazil"),
    Airport("GIG", "Rio de Janeiro/Galeao", "Rio de Janeiro", "Brazil"),
    Airport("EZE", "Ministro Pistarini", "Buenos Aires", "Argentina"),
    Airport("SCL", "Arturo Merino Benitez", "Santiago", "Chile"),
    Airport("BOG", "El Dorado International", "Bogota", "Colombia"),
    Airport("LIM", "Jorge Chavez International", "Lima", "Peru"),
    Airport("MEX", "Benito Juarez International", "Mexico City", "Mexico"),
    Airport("CUN", "Cancun International", "Cancun", "Mexico"),
]

_BY_CODE = {a.code: a for a in AIRPORTS}
# First-listed airport wins for multi-airport cities (e.g. New York -> JFK).
_BY_CITY: dict[str, Airport] = {}
for _a in AIRPORTS:
    _BY_CITY.setdefault(_a.city.lower(), _a)


def resolve_airport(value: str) -> str:
    """Return the IATA code for ``value`` (a code, city, or airport name).

    Raises ``ValueError`` if the input cannot be mapped to an airport.
    """

    if value is None:
        raise ValueError("Airport is required")
    text = value.strip()
    if not text:
        raise ValueError("Airport is required")

    # A bare 3-letter code is accepted directly (SerpAPI supports any valid IATA).
    if _CODE_RE.match(text):
        return text.upper()

    q = text.lower()
    # Exact city match first, then substring against city / name / country.
    if q in _BY_CITY:
        return _BY_CITY[q].code
    for a in AIRPORTS:
        if q == a.name.lower():
            return a.code
    for a in AIRPORTS:
        if q in a.city.lower() or q in a.name.lower() or q in a.country.lower():
            return a.code

    raise ValueError(
        f"Could not resolve '{value}' to an airport. Use an IATA code (e.g. DAC) "
        "or a known city/airport name."
    )
