# ParetoFly

> An opinionated flight agent. Instead of returning a sortable wall of 200 results,
> it returns **three Pareto-optimal itineraries** with honest, grounded pros/cons.

Metasearch makes *you* the ranking engine — you compare tabs, mentally add bag
fees, and guess whether a 90-minute layover in FRA is survivable. ParetoFly does
that work: it parses your constraints (structured **and** fuzzy), normalizes
**true cost**, scores every candidate on 8 weighted features, and explains the
trade-offs in plain English.

**Recommend-only** by design: no booking, no payments, no PII persisted.

- Concept & research: [docs/PARETOFLY.md](docs/PARETOFLY.md)
- Codebase walkthrough: [docs/CODEBASE_GUIDE.md](docs/CODEBASE_GUIDE.md)
- Orchestration internals: [docs/LANGGRAPH_GUIDE.md](docs/LANGGRAPH_GUIDE.md)
- Roadmap & changelog: [PROGRESS.md](PROGRESS.md)

---

## Status

| Component | State |
|---|---|
| Agent pipeline (LangGraph) | ✅ Done |
| HTTP API (FastAPI + SSE) | ✅ Done |
| SerpAPI TTL response cache | ✅ Done |
| Persona-inferred scoring weights | ✅ Done |
| Frontend (Next.js / TS / Tailwind) | ✅ MVP — form, live progress, top-3 |
| Tests | ✅ 30 passing (network mocked) |
| Runtime | Python 3.14.5 |

---

## Architecture

The agent is a LangGraph state machine. Each node is a small, single-purpose
function that reads and writes a shared `GraphState`; conditional edges skip
downstream work when a search fails or returns nothing.

```
TripQuery
   │
   ▼
intake → search → enrich → score → rank → explain → present
   │        │        │        │       │       │
GPT-5-mini SerpAPI  Serper   pure-  top-3   GPT-5
+ persona  flights  bag fees  Python diverse prose
```

| Node | Responsibility | External dep | Fallback |
|---|---|---|---|
| `intake` | Free-text → `ParsedSignals`; `infer_persona()` picks default weights | GPT-5-mini | Form-derived signals |
| `search` | Fetch + normalize offers | SerpAPI (cached) | `SerpApiError` → clean error state |
| `enrich` | Baggage-fee lookup → `true_price` (only if checked bags) | Serper + GPT-5-mini | Default fee constant |
| `score` | 8-feature min-max weighted scoring | — (pure) | n/a |
| `rank` | Diversity-aware top-3 (drops near-duplicates) | — (pure) | n/a |
| `explain` | Rule-based pros/cons, then GPT-5 rewrite | GPT-5 | Rule-based baseline |
| `present` | Terminal node (CLI prints / SSE closes) | — | n/a |

**Design principle — degrade gracefully.** Every node that touches the network or
an LLM has a deterministic fallback. A flaky model or web call never crashes a
recommendation; worst case, the output is slightly less polished.

**Scoring features:** price, duration, stops, layover quality, arrival-time fit
(Gaussian around the preferred window + red-eye penalty), reliability, aircraft
match, carbon. Weights come from the inferred persona (`student` / `business` /
`family`) and can be overridden per request.

---

## Tech stack

Python 3.14 · Pydantic v2 · LangGraph · LangChain (Azure GPT-5 / GPT-5-mini) ·
httpx · FastAPI + sse-starlette · pytest.
Data: **SerpAPI Google Flights** (offers) + **Serper.dev** (web enrichment).
Frontend: Next.js App Router + TypeScript + Tailwind.

> **SerpAPI ≠ Serper.** `SERPAPI_API_KEY` (serpapi.com) = flight offers;
> `SERPER_API_KEY` (serper.dev) = web enrichment. Different vendors, easily confused.

---

## Layout

```
app/
  config.py            # pydantic-settings loader (.env, alias-tolerant)
  models/schemas.py    # data contracts — start here
  tools/               # I/O to the outside world
    serpapi_flights.py #   flight offers
    serper.py          #   web search (enrichment)
    flight_cache.py    #   on-disk TTL cache for SerpAPI
  scoring/model.py     # scoring + diversity ranking (pure)
  enrichment.py        # baggage fees → true price
  llm/                 # Azure clients, intake parse, explain narrative
  graph/               # state.py, nodes.py, build.py (the state machine)
  api/main.py          # /health, /search, /search/stream
  cli.py               # local harness
frontend/              # Next.js UI (see frontend/README.md)
tests/                 # unit + integration, all network mocked
docs/                  # concept + engineering guides
```

Placement rule: external HTTP → `tools/`; LLM calls → `llm/`; pure logic →
`scoring/` or a plain module; orchestration → `graph/`; HTTP surface → `api/`.

---

## Quickstart

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env    # then fill in real values
```

### Frontend

```bash
cd frontend
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_BASE_URL if not localhost:8000
npm install
```

### Run

```powershell
# API (Swagger at http://localhost:8000/docs)
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload

# UI (separate terminal) → http://localhost:3000
cd frontend; npm run dev

# End-to-end pipeline against live data (spends 1 SerpAPI search unless cached)
.\.venv\Scripts\python.exe -m app.cli --from JFK --to LAX --depart 2026-08-15 `
  --adults 2 --note "afternoon arrival, no red-eyes, 2 checked bags" --run

# Tests
.\.venv\Scripts\python.exe -m pytest -q
```

**CLI flags:** `--from`, `--to`, `--depart` (required); `--return`, `--adults`,
`--children`, `--infants`, `--cabin`, `--max-stops`, `--budget`, `--max-layover`,
`--note`, `--currency`; mode: `--search` (raw offers) or `--run` (full pipeline).

---

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness → `{"status": "ok"}` |
| `POST` | `/search` | Body = `TripQuery`; returns top-3 as JSON |
| `POST` | `/search/stream` | Same, streamed as SSE: one `progress` event per node, then a terminal `result` event |

`/search/stream` is what the UI consumes for the live "Searching… Scoring…
Explaining…" timeline. Native `EventSource` can't POST, so the frontend uses
`@microsoft/fetch-event-source`.

---

## Configuration

All settings load from `.env` (git-ignored; `.env.example` is the reference). The
loader is alias-tolerant and case-insensitive.

| Variable | Default | Purpose |
|---|---|---|
| `SERPAPI_API_KEY` (alias `SerpApi_key`) | — | Flight offers |
| `SERPER_API_KEY` | — | Web enrichment (baggage fees) |
| `AZURE_GPT5_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT` | `gpt-5` | Narrative / explain |
| `AZURE_GPT5_MINI_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT` | `gpt-5-mini` | Intake / extraction |
| `AZURE_GPT5*_API_VERSION` | `2024-12-01-preview` | Azure API version |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `SERPAPI_CACHE_ENABLED` | `true` | Toggle the offer cache |
| `SERPAPI_CACHE_DIR` | `.cache/serpapi` | Cache location |
| `SERPAPI_CACHE_TTL_SECONDS` | `21600` (6h) | Cache freshness window |

---

## Design notes & constraints

- **Why SerpAPI:** Amadeus self-service was decommissioned (Jul 2025). SerpAPI
  Google Flights is free at **250 searches/month** and already carries ~7 of the 8
  scoring features. That budget is the hard constraint the cache exists to protect
  — every *uncached* search spends 1 of 250.
- **LLM split:** GPT-5-mini does cheap/fast structured extraction; GPT-5 writes
  narrative only. GPT-5 reasoning latency (tens of seconds) is expected, not a bug
  — hence SSE progress so the UI never looks frozen.
- **Grounding:** the explain node always computes rule-based pros/cons first and
  passes them to GPT-5 as the source of truth, so the narrative can't hallucinate
  facts that aren't in the data.
- **Zero-offer routes:** some route/date/filter combos legitimately return no
  offers from Google Flights; this surfaces as a clean error, not a stack trace.
- **Secrets:** never commit `.env`.
- **Windows/PowerShell:** `>` redirects write UTF-16 — read back with
  `Get-Content -Encoding Unicode`. The CLI forces UTF-8 stdout so em-dashes render.
