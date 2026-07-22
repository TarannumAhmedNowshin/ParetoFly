# ParetoFly

A weekend project: I needed to book a flight, so instead of messaging a travel
agent I built an AI one. You write your requirements in your own words — "cheapest
option, student fares if any, no red-eyes, arriving before noon" — and it searches
flights, works out the real price (fare plus baggage fees and any student discounts
it can actually find and cite, converted at the real-time currency rate), and
returns three genuinely different options, each with an honest explanation of the
trade-off.

It is recommend-only: no booking, no payments, no persisted PII.

## What it does

- **Understands preferences written in plain English.** A note like "afternoon
  arrival, no red-eyes, traveling with a toddler, 2 checked bags" is parsed into
  structured signals — arrival window, red-eye avoidance, family travel, baggage
  needs — and folded into the ranking, alongside the usual form fields.
- **Finds discounts the listing price hides.** For each airline it runs live web
  searches to surface student fares and booking-portal promotions, then verifies
  and extracts them with an LLM. Every discount it reports is backed by a citation
  (the source sentence, the URL, and a confidence score) so nothing is invented.
- **Ranks on what you actually pay.** Advertised fares omit checked-baggage fees,
  student discounts, and carry-on allowances. The agent enriches each option with
  those real costs and ranks on the resulting true price, not the sticker price.
- **Adapts to who is traveling.** It infers a persona — student, business, or
  family — and shifts the scoring weights accordingly (a student is optimized for
  price, a business traveler for schedule and reliability). Weights can also be set
  explicitly, and an eco mode brings carbon emissions into the ranking.
- **Returns three genuinely different options, each explained.** Instead of near-
  duplicate results, it selects a diverse top three and writes a short, grounded
  rationale for each — the trade-off it represents and its concrete pros and cons.
- **Handles currencies and messy input.** Fares are converted to the requested
  currency when the data source falls back to another, and cities or airport names
  are resolved to IATA codes so "Dhaka" and "DAC" both work.
- **Streams progress live.** The API emits an event per pipeline stage over SSE, so
  the UI shows a real-time "searching, enriching, scoring, explaining" timeline
  instead of a spinner, and each search produces a downloadable Markdown report.

## Architecture

The agent is a LangGraph state machine. Each node is a single-purpose function
that reads and writes a shared `GraphState`; a conditional edge after `search`
skips the downstream pipeline when a search fails or returns no offers.

```
intake → search → enrich → convert → score → rank → explain → present
```

| Node | Responsibility | External dependency | Fallback |
|---|---|---|---|
| `intake` | Parse free text into `ParsedSignals`; infer a persona to seed default weights | GPT-5-mini | Form-derived signals |
| `search` | Fetch and normalize offers | SerpAPI (cached) | `SerpApiError` → clean error state |
| `enrich` | Fold baggage fees, student/portal discounts, and allowances into `true_price` | Web-knowledge chain + GPT-5-mini | Default fee constant; discounts skipped |
| `convert` | Convert fares to the requested currency when search fell back to another | Keyless FX API (cached) | Keep original currency |
| `score` | Nine-feature min-max weighted scoring | none (pure) | — |
| `rank` | Diversity-aware top-3 selection | none (pure) | — |
| `explain` | Rule-based pros/cons, then an LLM rewrite | GPT-5 | Rule-based baseline |
| `present` | Terminal node (CLI print / SSE close) | none | — |

Every node that touches the network or an LLM has a deterministic fallback, so a
model or upstream failure degrades output quality rather than crashing a request.

Scoring and ranking are pure Python — no I/O, no LLM — which keeps ranking
decisions deterministic and fully unit-testable. LLMs are used only for parsing
fuzzy intent and writing narrative. The explanation node computes rule-based
pros/cons first and passes them to the LLM as the source of truth, so the prose
cannot introduce facts absent from the data.

### Scoring

Each candidate is scored on nine features normalized to `[0, 1]`: price, duration,
stops, layover quality, arrival-time fit (a Gaussian around the preferred window
with a red-eye penalty), reliability, aircraft match, carbon, and luggage fit.
Weights default from an inferred persona (`student`, `business`, or `family`) and
can be overridden per request. Carbon only affects ranking when the traveler opts
into eco mode; otherwise its weight is redistributed across the other features.

### Web enrichment

Enrichment resolves short factual snippets (baggage fees, student programs,
allowances) through a provider chain that returns the first non-empty result:
Serper, then a keyless DuckDuckGo endpoint, then headless Playwright. A circuit
breaker cools a failing provider before it is retried. For each distinct airline
the enricher performs one web lookup and one LLM extraction into a typed model,
runs airlines concurrently, and caches results on disk for 14 days. Each reported
discount carries provenance: the supporting sentence, the source URL, and a
confidence score.

## Tech stack

- Backend: Python 3.14, Pydantic v2, LangGraph, LangChain (Azure GPT-5 /
  GPT-5-mini), FastAPI with `sse-starlette`, httpx, Playwright, pytest.
- Frontend: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4,
  `@microsoft/fetch-event-source`.
- Data sources: SerpAPI Google Flights (offers); Serper, DuckDuckGo, and
  Playwright (web enrichment); open.er-api.com (FX rates).

SerpAPI and Serper are different vendors: `SERPAPI_API_KEY` (serpapi.com) provides
flight offers; `SERPER_API_KEY` (serper.dev) provides web enrichment.

## Project layout

```
app/
  config.py            pydantic-settings loader (.env, alias-tolerant)
  airports.py          city/name to IATA resolution
  logging_config.py    session-bound structured logging
  models/schemas.py    data contracts
  tools/
    serpapi_flights.py flight offers
    serper.py          web search
    web_knowledge.py   provider chain with circuit breaker
    kb_cache.py        on-disk TTL cache (enrichment, FX)
    flight_cache.py    on-disk TTL cache for SerpAPI offers
    fx.py              currency conversion
  scoring/model.py     scoring and diversity ranking (pure)
  enrichment.py        true-cost enrichment
  reporting.py         downloadable per-search Markdown reports
  llm/                 Azure clients, intake parsing, explanation
  graph/               state.py, nodes.py, build.py
  api/main.py          /health, /search, /search/stream, /report/{id}
  cli.py               local harness
frontend/              Next.js UI
tests/                 unit and integration tests (network mocked)
docs/                  concept and engineering guides
```

Placement convention: external HTTP in `tools/`, LLM calls in `llm/`, pure logic
in `scoring/` or a plain module, orchestration in `graph/`, HTTP surface in `api/`.

## Getting started

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium   # optional web-search fallback
Copy-Item .env.example .env                                 # then fill in real values
```

Frontend:

```bash
cd frontend
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_BASE_URL if not localhost:8000
npm install
```

Run:

```powershell
# API (Swagger at http://localhost:8000/docs)
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload

# UI (separate terminal, http://localhost:3000)
cd frontend; npm run dev

# End-to-end pipeline against live data (spends one SerpAPI search unless cached)
.\.venv\Scripts\python.exe -m app.cli --from JFK --to LAX --depart 2026-08-15 `
  --adults 2 --note "afternoon arrival, no red-eyes, 2 checked bags" --run

# Tests (network mocked)
.\.venv\Scripts\python.exe -m pytest -q
```

CLI flags: `--from`, `--to`, and `--depart` are required; `--return`, `--adults`,
`--children`, `--infants`, `--cabin`, `--max-stops`, `--budget`, `--max-layover`,
`--note`, and `--currency` are optional. Use `--search` for raw offers or `--run`
for the full pipeline.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `POST` | `/search` | Body is a `TripQuery`; runs the pipeline, saves a report, returns the top three |
| `POST` | `/search/stream` | Same, streamed as SSE: one `progress` event per node, then a terminal `result` event |
| `GET` | `/report/{session_id}` | Download a search's recommendations as a Markdown report |

The frontend consumes `/search/stream` for a live progress timeline. Because the
native `EventSource` API cannot issue a POST, the client uses
`@microsoft/fetch-event-source`. Each search is assigned a `session_id` that binds
its logs and its downloadable report.

## Configuration

Settings load from `.env` (git-ignored; `.env.example` is the reference). The
loader is alias-tolerant and case-insensitive.

| Variable | Default | Purpose |
|---|---|---|
| `SERPAPI_API_KEY` (alias `SerpApi_key`) | — | Flight offers |
| `SERPER_API_KEY` | — | Web enrichment (primary provider) |
| `AZURE_GPT5_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT` | `gpt-5` | Narrative and explanation |
| `AZURE_GPT5_MINI_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT` | `gpt-5-mini` | Intake and extraction |
| `AZURE_GPT5*_API_VERSION` | `2024-12-01-preview` | Azure API version |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `SERPAPI_CACHE_ENABLED` | `true` | Toggle the offer cache |
| `SERPAPI_CACHE_DIR` / `_TTL_SECONDS` | `.cache/serpapi` / `21600` | Offer cache location and freshness |
| `KB_CACHE_DIR` / `_TTL_SECONDS` | `.cache/kb` / `1209600` | Enrichment knowledge cache |
| `FX_CACHE_DIR` / `_TTL_SECONDS` | `.cache/fx` | FX rate cache |
| `ENRICH_MAX_WORKERS` | `6` | Concurrency for per-airline enrichment |
| `REPORTS_DIR` | `reports` | Directory for generated reports |

## Notes

- SerpAPI Google Flights is the offer source because Amadeus self-service was
  decommissioned in July 2025. The free tier allows 250 searches per month; the
  caches exist to protect that limit, since every uncached search consumes one.
- GPT-5-mini handles structured extraction; GPT-5 writes narrative only. GPT-5
  reasoning latency of tens of seconds is expected, which is why the API streams
  progress.
- Some route, date, and filter combinations legitimately return no offers; the
  pipeline surfaces this as a clean error rather than a stack trace.
- On Windows PowerShell, `>` redirects write UTF-16; read them back with
  `Get-Content -Encoding Unicode`. The CLI forces UTF-8 stdout.

## Tests

The suite covers scoring, ranking, the pipeline, enrichment, caching, FX, the
web-knowledge fallback chain, and the API. All network calls are mocked, so the
tests run fast and consume no API budget.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
