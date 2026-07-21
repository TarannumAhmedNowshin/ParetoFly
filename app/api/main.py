"""FastAPI gateway exposing the ParetoFly pipeline.

Endpoints:
- ``GET  /health``          liveness probe.
- ``POST /search``          run the full pipeline, return the top-3 as JSON.
- ``POST /search/stream``   same, but stream node-by-node progress via SSE.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.graph import build_graph
from app.graph.state import GraphState
from app.models.schemas import Recommendation, TripQuery

app = FastAPI(title="ParetoFly", version="0.1.0")

# Allow the Next.js frontend (configurable via CORS_ALLOW_ORIGINS) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compile the graph once at import time and reuse it across requests.
_graph = build_graph()


def _serialize(state: GraphState) -> dict[str, Any]:
    recs: list[Recommendation] = state.get("recommendations", []) or []
    return {
        "error": state.get("error"),
        "log": state.get("log", []),
        "recommendations": [r.model_dump(mode="json") for r in recs],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search")
async def search(query: TripQuery) -> dict[str, Any]:
    """Run the pipeline and return the final recommendations."""

    initial: GraphState = {"query": query, "log": []}
    state = await _graph.ainvoke(initial)
    return _serialize(state)


@app.post("/search/stream")
async def search_stream(query: TripQuery) -> EventSourceResponse:
    """Stream node progress, then a terminal ``result`` event."""

    initial: GraphState = {"query": query, "log": []}

    async def event_generator():
        final: GraphState = {}
        async for chunk in _graph.astream(initial):
            for node_name, update in chunk.items():
                final.update(update)
                log = update.get("log")
                message = log[-1] if log else node_name
                yield {"event": "progress", "data": json.dumps({"node": node_name, "message": message})}
        yield {"event": "result", "data": json.dumps(_serialize(final))}

    return EventSourceResponse(event_generator())
