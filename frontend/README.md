# ParetoFly — Frontend

Next.js (App Router) + TypeScript + Tailwind UI for the ParetoFly agent. It sends
a hybrid intake form + free-text note to the backend and renders live pipeline
progress plus the top-3 Pareto-optimal flights.

## Prerequisites

- Node.js 20+ (tested on Node 24)
- The ParetoFly FastAPI backend running (default `http://localhost:8000`)

## Setup

```bash
cp .env.local.example .env.local   # adjust NEXT_PUBLIC_API_BASE_URL if needed
npm install
npm run dev                        # http://localhost:3000
```

## How it works

- `src/types/api.ts` — TypeScript mirrors of the backend Pydantic schemas.
- `src/lib/api.ts` — `searchStream()` posts a `TripQuery` to `POST /search/stream`
  and consumes Server-Sent Events with `@microsoft/fetch-event-source` (native
  `EventSource` can't POST). `search()` is a non-streaming fallback.
- `src/components/SearchForm.tsx` — hybrid intake form + free-text box + advanced
  refine panel (budget, max stops, persona override).
- `src/components/ProgressTimeline.tsx` — live pipeline stages from `progress` events.
- `src/components/ResultCard.tsx` / `FeatureScores.tsx` — top-3 render with pros/cons,
  true price, and the 8-feature score breakdown.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend base URL |

Make sure the backend's `CORS_ALLOW_ORIGINS` includes this app's origin
(`http://localhost:3000` by default).
