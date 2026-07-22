"""Assemble and run the ParetoFly LangGraph pipeline."""

from __future__ import annotations

from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    convert_node,
    enrich_node,
    explain_node,
    intake_node,
    present_node,
    rank_node,
    score_node,
    search_node,
)
from app.graph.state import GraphState
from app.logging_config import bind_session
from app.models.schemas import TripQuery


def _has_offers(state: GraphState) -> str:
    """Route to enrichment only when the search produced offers."""

    if state.get("error") or not state.get("offers"):
        return "present"
    return "enrich"


def build_graph():
    """Build and compile the agent state machine."""

    graph = StateGraph(GraphState)
    graph.add_node("intake", intake_node)
    graph.add_node("search", search_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("convert", convert_node)
    graph.add_node("score", score_node)
    graph.add_node("rank", rank_node)
    graph.add_node("explain", explain_node)
    graph.add_node("present", present_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "search")
    graph.add_conditional_edges("search", _has_offers, {"enrich": "enrich", "present": "present"})
    graph.add_edge("enrich", "convert")
    graph.add_edge("convert", "score")
    graph.add_edge("score", "rank")
    graph.add_edge("rank", "explain")
    graph.add_edge("explain", "present")
    graph.add_edge("present", END)

    return graph.compile()


def run_pipeline(query: TripQuery) -> GraphState:
    """Convenience helper: run the full pipeline for a query and return final state."""

    app = build_graph()
    session_id = uuid4().hex
    with bind_session(session_id):
        initial: GraphState = {"query": query, "log": [], "session_id": session_id}
        return app.invoke(initial)
