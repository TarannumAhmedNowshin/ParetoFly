"""FastAPI gateway exposing the ParetoFly pipeline.

Endpoints:
- ``GET  /health``          liveness probe.
- ``POST /search``          run the full pipeline, return the top-3 as JSON.
- ``POST /search/stream``   same, but stream node-by-node progress via SSE.
"""

from __future__ import annotations

import json
from uuid import uuid4
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.graph import build_graph
from app.graph.state import GraphState
from app.models.schemas import Recommendation, TripQuery
from app.reporting import is_valid_session_id, report_path, save_report

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


def _serialize(state: GraphState, session_id: str | None = None) -> dict[str, Any]:
    recs: list[Recommendation] = state.get("recommendations", []) or []
    return {
        "session_id": session_id,
        "error": state.get("error"),
        "log": state.get("log", []),
        "recommendations": [r.model_dump(mode="json") for r in recs],
    }


def _persist_report(session_id: str, state: GraphState) -> None:
    """Best-effort report save; never fail the request over report I/O."""

    query = state.get("query")
    if query is None:
        return
    try:
        save_report(session_id, query, state.get("recommendations", []) or [])
    except Exception:  # pragma: no cover - report persistence must not break search
        pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search")
async def search(query: TripQuery) -> dict[str, Any]:
    """Run the pipeline, save a downloadable report, return recommendations."""

    session_id = uuid4().hex
    initial: GraphState = {"query": query, "log": []}
    state = await _graph.ainvoke(initial)
    _persist_report(session_id, state)
    return _serialize(state, session_id)


@app.post("/search/stream")
async def search_stream(query: TripQuery) -> EventSourceResponse:
    """Stream node progress, then a terminal ``result`` event."""

    session_id = uuid4().hex
    initial: GraphState = {"query": query, "log": []}

    async def event_generator():
        final: GraphState = {"query": query}
        async for chunk in _graph.astream(initial):
            for node_name, update in chunk.items():
                final.update(update)
                log = update.get("log")
                message = log[-1] if log else node_name
                yield {"event": "progress", "data": json.dumps({"node": node_name, "message": message})}
        _persist_report(session_id, final)
        yield {"event": "result", "data": json.dumps(_serialize(final, session_id))}

    return EventSourceResponse(event_generator())


@app.get("/report/{session_id}")
def download_report(session_id: str) -> FileResponse:
    """Download a previously generated report as a Markdown attachment."""

    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")
    path = report_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    filename = f"{session_id}_report.md"
    return FileResponse(
        path,
        media_type="text/markdown",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
