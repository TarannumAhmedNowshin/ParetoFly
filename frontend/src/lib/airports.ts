// Curated list of major world airports for the From/To autocomplete.
// Users can search by city, country, airport name, or IATA code; the form
// still submits the 3-letter IATA `code` that the backend / SerpAPI expects.

export interface Airport {
  code: string; // IATA (e.g. "DAC")
  name: string; // Airport name (e.g. "Hazrat Shahjalal International")
  city: string;
  country: string;
}

export const AIRPORTS: Airport[] = [
  { code: "DAC", name: "Hazrat Shahjalal International", city: "Dhaka", country: "Bangladesh" },
  { code: "CGP", name: "Shah Amanat International", city: "Chattogram", country: "Bangladesh" },
  { code: "JFK", name: "John F. Kennedy International", city: "New York", country: "United States" },
  { code: "EWR", name: "Newark Liberty International", city: "Newark", country: "United States" },
  { code: "LGA", name: "LaGuardia", city: "New York", country: "United States" },
  { code: "LAX", name: "Los Angeles International", city: "Los Angeles", country: "United States" },
  { code: "SFO", name: "San Francisco International", city: "San Francisco", country: "United States" },
  { code: "ORD", name: "O'Hare International", city: "Chicago", country: "United States" },
  { code: "ATL", name: "Hartsfield-Jackson", city: "Atlanta", country: "United States" },
  { code: "DFW", name: "Dallas/Fort Worth International", city: "Dallas", country: "United States" },
  { code: "SEA", name: "Seattle-Tacoma International", city: "Seattle", country: "United States" },
  { code: "MIA", name: "Miami International", city: "Miami", country: "United States" },
  { code: "BOS", name: "Logan International", city: "Boston", country: "United States" },
  { code: "IAD", name: "Washington Dulles International", city: "Washington", country: "United States" },
  { code: "DEN", name: "Denver International", city: "Denver", country: "United States" },
  { code: "LAS", name: "Harry Reid International", city: "Las Vegas", country: "United States" },
  { code: "YYZ", name: "Toronto Pearson International", city: "Toronto", country: "Canada" },
  { code: "YVR", name: "Vancouver International", city: "Vancouver", country: "Canada" },
  { code: "LHR", name: "Heathrow", city: "London", country: "United Kingdom" },
  { code: "LGW", name: "Gatwick", city: "London", country: "United Kingdom" },
  { code: "MAN", name: "Manchester", city: "Manchester", country: "United Kingdom" },
  { code: "CDG", name: "Charles de Gaulle", city: "Paris", country: "France" },
  { code: "ORY", name: "Orly", city: "Paris", country: "France" },
  { code: "AMS", name: "Schiphol", city: "Amsterdam", country: "Netherlands" },
  { code: "FRA", name: "Frankfurt International", city: "Frankfurt", country: "Germany" },
  { code: "MUC", name: "Munich International", city: "Munich", country: "Germany" },
  { code: "MAD", name: "Adolfo Suarez Madrid-Barajas", city: "Madrid", country: "Spain" },
  { code: "BCN", name: "Barcelona-El Prat", city: "Barcelona", country: "Spain" },
  { code: "FCO", name: "Leonardo da Vinci-Fiumicino", city: "Rome", country: "Italy" },
  { code: "MXP", name: "Milan Malpensa", city: "Milan", country: "Italy" },
  { code: "ZRH", name: "Zurich", city: "Zurich", country: "Switzerland" },
  { code: "VIE", name: "Vienna International", city: "Vienna", country: "Austria" },
  { code: "CPH", name: "Copenhagen", city: "Copenhagen", country: "Denmark" },
  { code: "ARN", name: "Stockholm Arlanda", city: "Stockholm", country: "Sweden" },
  { code: "OSL", name: "Oslo Gardermoen", city: "Oslo", country: "Norway" },
  { code: "HEL", name: "Helsinki-Vantaa", city: "Helsinki", country: "Finland" },
  { code: "DUB", name: "Dublin", city: "Dublin", country: "Ireland" },
  { code: "LIS", name: "Humberto Delgado", city: "Lisbon", country: "Portugal" },
  { code: "IST", name: "Istanbul", city: "Istanbul", country: "Turkey" },
  { code: "SVO", name: "Sheremetyevo", city: "Moscow", country: "Russia" },
  { code: "DXB", name: "Dubai International", city: "Dubai", country: "United Arab Emirates" },
  { code: "AUH", name: "Abu Dhabi International", city: "Abu Dhabi", country: "United Arab Emirates" },
  { code: "DOH", name: "Hamad International", city: "Doha", country: "Qatar" },
  { code: "RUH", name: "King Khalid International", city: "Riyadh", country: "Saudi Arabia" },
  { code: "JED", name: "King Abdulaziz International", city: "Jeddah", country: "Saudi Arabia" },
  { code: "KWI", name: "Kuwait International", city: "Kuwait City", country: "Kuwait" },
  { code: "DEL", name: "Indira Gandhi International", city: "Delhi", country: "India" },
  { code: "BOM", name: "Chhatrapati Shivaji Maharaj", city: "Mumbai", country: "India" },
  { code: "BLR", name: "Kempegowda International", city: "Bengaluru", country: "India" },
  { code: "MAA", name: "Chennai International", city: "Chennai", country: "India" },
  { code: "CCU", name: "Netaji Subhas Chandra Bose", city: "Kolkata", country: "India" },
  { code: "HYD", name: "Rajiv Gandhi International", city: "Hyderabad", country: "India" },
  { code: "KTM", name: "Tribhuvan International", city: "Kathmandu", country: "Nepal" },
  { code: "CMB", name: "Bandaranaike International", city: "Colombo", country: "Sri Lanka" },
  { code: "KHI", name: "Jinnah International", city: "Karachi", country: "Pakistan" },
  { code: "LHE", name: "Allama Iqbal International", city: "Lahore", country: "Pakistan" },
  { code: "ISB", name: "Islamabad International", city: "Islamabad", country: "Pakistan" },
  { code: "BKK", name: "Suvarnabhumi", city: "Bangkok", country: "Thailand" },
  { code: "DMK", name: "Don Mueang International", city: "Bangkok", country: "Thailand" },
  { code: "SIN", name: "Changi", city: "Singapore", country: "Singapore" },
  { code: "KUL", name: "Kuala Lumpur International", city: "Kuala Lumpur", country: "Malaysia" },
  { code: "CGK", name: "Soekarno-Hatta International", city: "Jakarta", country: "Indonesia" },
  { code: "DPS", name: "Ngurah Rai International", city: "Bali", country: "Indonesia" },
  { code: "MNL", name: "Ninoy Aquino International", city: "Manila", country: "Philippines" },
  { code: "HAN", name: "Noi Bai International", city: "Hanoi", country: "Vietnam" },
  { code: "SGN", name: "Tan Son Nhat International", city: "Ho Chi Minh City", country: "Vietnam" },
  { code: "HKG", name: "Hong Kong International", city: "Hong Kong", country: "Hong Kong" },
  { code: "TPE", name: "Taoyuan International", city: "Taipei", country: "Taiwan" },
  { code: "ICN", name: "Incheon International", city: "Seoul", country: "South Korea" },
  { code: "NRT", name: "Narita International", city: "Tokyo", country: "Japan" },
  { code: "HND", name: "Haneda", city: "Tokyo", country: "Japan" },
  { code: "KIX", name: "Kansai International", city: "Osaka", country: "Japan" },
  { code: "PEK", name: "Beijing Capital International", city: "Beijing", country: "China" },
  { code: "PVG", name: "Shanghai Pudong International", city: "Shanghai", country: "China" },
  { code: "CAN", name: "Guangzhou Baiyun International", city: "Guangzhou", country: "China" },
  { code: "SYD", name: "Kingsford Smith", city: "Sydney", country: "Australia" },
  { code: "MEL", name: "Melbourne", city: "Melbourne", country: "Australia" },
  { code: "BNE", name: "Brisbane", city: "Brisbane", country: "Australia" },
  { code: "AKL", name: "Auckland", city: "Auckland", country: "New Zealand" },
  { code: "JNB", name: "O. R. Tambo International", city: "Johannesburg", country: "South Africa" },
  { code: "CPT", name: "Cape Town International", city: "Cape Town", country: "South Africa" },
  { code: "CAI", name: "Cairo International", city: "Cairo", country: "Egypt" },
  { code: "NBO", name: "Jomo Kenyatta International", city: "Nairobi", country: "Kenya" },
  { code: "ADD", name: "Bole International", city: "Addis Ababa", country: "Ethiopia" },
  { code: "LOS", name: "Murtala Muhammed International", city: "Lagos", country: "Nigeria" },
  { code: "GRU", name: "Sao Paulo/Guarulhos", city: "Sao Paulo", country: "Brazil" },
  { code: "GIG", name: "Rio de Janeiro/Galeao", city: "Rio de Janeiro", country: "Brazil" },
  { code: "EZE", name: "Ministro Pistarini", city: "Buenos Aires", country: "Argentina" },
  { code: "SCL", name: "Arturo Merino Benitez", city: "Santiago", country: "Chile" },
  { code: "BOG", name: "El Dorado International", city: "Bogota", country: "Colombia" },
  { code: "LIM", name: "Jorge Chavez International", city: "Lima", country: "Peru" },
  { code: "MEX", name: "Benito Juarez International", city: "Mexico City", country: "Mexico" },
  { code: "CUN", name: "Cancun International", city: "Cancun", country: "Mexico" },
];

/** A short human-friendly label, e.g. "Dhaka, Bangladesh — Hazrat Shahjalal (DAC)". */
export function airportLabel(a: Airport): string {
  return `${a.city}, ${a.country} — ${a.name} (${a.code})`;
}

const AIRPORT_BY_CODE = new Map(AIRPORTS.map((a) => [a.code, a]));

export function findAirport(code: string): Airport | undefined {
  return AIRPORT_BY_CODE.get(code.trim().toUpperCase());
}

/** Rank airports against a free-text query. Returns up to `limit` matches. */
export function searchAirports(query: string, limit = 8): Airport[] {
  const q = query.trim().toLowerCase();
  if (!q) return AIRPORTS.slice(0, limit);

  const scored: { airport: Airport; score: number }[] = [];
  for (const a of AIRPORTS) {
    const code = a.code.toLowerCase();
    const city = a.city.toLowerCase();
    const country = a.country.toLowerCase();
    const name = a.name.toLowerCase();

    let score = 0;
    if (code === q) score = 100;
    else if (city === q) score = 90;
    else if (code.startsWith(q)) score = 80;
    else if (city.startsWith(q)) score = 70;
    else if (name.startsWith(q)) score = 55;
    else if (country.startsWith(q)) score = 45;
    else if (city.includes(q)) score = 40;
    else if (name.includes(q)) score = 30;
    else if (country.includes(q)) score = 20;
    else if (code.includes(q)) score = 15;

    if (score > 0) scored.push({ airport: a, score });
  }

  scored.sort((x, y) => y.score - x.score || x.airport.city.localeCompare(y.airport.city));
  return scored.slice(0, limit).map((s) => s.airport);
}
