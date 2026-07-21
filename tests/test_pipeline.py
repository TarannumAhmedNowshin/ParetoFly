"""Pipeline integration test with a mocked flight source (no network)."""

from __future__ import annotations

from datetime import date

from app.graph import nodes, run_pipeline
from app.models.schemas import ParsedSignals, TripQuery
from app.tools import SerpApiError
from tests.conftest import make_offers


def _query() -> TripQuery:
    return TripQuery(origin="DAC", destination="JFK", depart_date=date(2026, 8, 12), children=1)


def _no_network(monkeypatch):
    """Stub out both external dependencies of the graph."""

    monkeypatch.setattr(nodes, "parse_free_text", lambda q: ParsedSignals(travel_with_child=True))
    # explain_node keeps its rule-based reasons when the LLM "fails".
    monkeypatch.setattr(nodes, "write_explanations", lambda recs, q: False)


def test_pipeline_produces_diverse_top3(monkeypatch):
    _no_network(monkeypatch)
    monkeypatch.setattr(nodes, "search_flights", lambda q: make_offers())
    state = run_pipeline(_query())

    assert state.get("error") is None
    recs = state["recommendations"]
    assert len(recs) == 3
    assert [r.rank for r in recs] == [1, 2, 3]
    for r in recs:
        assert r.narrative
        assert r.pros
    ids = {r.scored.offer.id for r in recs}
    assert not {"balanced", "balanced_dupe"}.issubset(ids)


def test_pipeline_handles_search_error(monkeypatch):
    _no_network(monkeypatch)

    def _boom(_q):
        raise SerpApiError("no results")

    monkeypatch.setattr(nodes, "search_flights", _boom)
    state = run_pipeline(_query())
    assert state["error"] == "no results"
    assert not state.get("recommendations")
