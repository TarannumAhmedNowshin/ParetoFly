"""API tests using FastAPI's TestClient with the pipeline mocked (no network)."""

from __future__ import annotations

import app.graph.nodes as nodes
import app.reporting as reporting
from app.models.schemas import ParsedSignals
from fastapi.testclient import TestClient
from tests.conftest import make_offers


def _stub_network(monkeypatch):
    monkeypatch.setattr(nodes, "search_flights", lambda q: make_offers())
    monkeypatch.setattr(nodes, "parse_free_text", lambda q: ParsedSignals())
    monkeypatch.setattr(nodes, "enrich_true_prices", lambda offers, q: 0)
    monkeypatch.setattr(nodes, "write_explanations", lambda recs, q: False)


def _payload() -> dict:
    return {"origin": "DAC", "destination": "JFK", "depart_date": "2026-08-12", "children": 1}


def test_health():
    from app.api.main import app

    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_search_returns_top3(monkeypatch):
    _stub_network(monkeypatch)
    from app.api.main import app

    client = TestClient(app)
    resp = client.post("/search", json=_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["recommendations"]) == 3
    assert body["recommendations"][0]["rank"] == 1
    assert body["recommendations"][0]["pros"]


def test_search_stream_emits_progress_and_result(monkeypatch):
    _stub_network(monkeypatch)
    from app.api.main import app

    client = TestClient(app)
    with client.stream("POST", "/search/stream", json=_payload()) as resp:
        assert resp.status_code == 200
        text = "".join(resp.iter_text())
    assert "event: progress" in text
    assert "event: result" in text
    assert "search" in text


def test_search_generates_downloadable_report(monkeypatch, tmp_path):
    _stub_network(monkeypatch)
    monkeypatch.setattr(reporting, "reports_dir", lambda: tmp_path)
    from app.api.main import app

    client = TestClient(app)
    resp = client.post("/search", json=_payload())
    body = resp.json()
    session_id = body["session_id"]
    assert session_id and reporting.is_valid_session_id(session_id)
    assert (tmp_path / f"{session_id}_report.md").exists()

    dl = client.get(f"/report/{session_id}")
    assert dl.status_code == 200
    assert "ParetoFly flight report" in dl.text
    assert "attachment" in dl.headers["content-disposition"]


def test_report_invalid_session_id_rejected():
    from app.api.main import app

    client = TestClient(app)
    assert client.get("/report/not-hex!").status_code == 400


def test_report_missing_returns_404(monkeypatch, tmp_path):
    monkeypatch.setattr(reporting, "reports_dir", lambda: tmp_path)
    from app.api.main import app

    client = TestClient(app)
    assert client.get("/report/deadbeefdeadbeef").status_code == 404
