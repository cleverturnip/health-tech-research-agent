"""Phase-3 research runner (slice 3) — the /research routes + auto-start on GATE-1 approve (TestClient)."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from health_tech_research_agent.webapp import research  # noqa: E402
from health_tech_research_agent.webapp.app import create_app  # noqa: E402
from health_tech_research_agent.webapp.config import WebConfig  # noqa: E402
from health_tech_research_agent.webapp.security import hash_password  # noqa: E402
from health_tech_research_agent.webapp.source import FixtureDashboardSource  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"
PASSWORD = "research-pw"


def _client(tmp_path, *, login=True):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    jobs = tmp_path / "jobs"
    calls = []
    config = WebConfig(session_secret="s", password_hash=hash_password(PASSWORD), jobs_dir=str(jobs))
    client = TestClient(create_app(config, src, start_research=lambda: calls.append("started")))
    if login:
        client.post("/login", data={"password": PASSWORD})
    return client, src, jobs, calls


def test_research_requires_login(tmp_path):
    client, _, _, _ = _client(tmp_path, login=False)
    r = client.get("/research", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_research_page_renders(tmp_path):
    client, _, _, _ = _client(tmp_path)
    r = client.get("/research")
    assert r.status_code == 200 and 'id="rstat"' in r.text and "Research run" in r.text


def test_research_status_empty_then_reflects_job(tmp_path):
    client, _, jobs, _ = _client(tmp_path)
    assert client.get("/research/status").json() == {}                      # no run yet
    research._write_status(jobs, {"state": "running", "total": 3, "completed": 1, "current_company": "Acme"})
    body = client.get("/research/status").json()
    assert body["state"] == "running" and body["completed"] == 1 and body["current_company"] == "Acme"


def test_approve_saves_candidates_and_auto_starts_research(tmp_path):
    client, src, _, calls = _client(tmp_path)
    r = client.post("/discover/approve",
                    json={"candidates": [{"company": "Acme Health", "why": "w", "signal": "s"}]})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] and data["redirect"] == "/research"
    assert calls == ["started"]                                             # research auto-started on approval
    assert "Acme Health" in (tmp_path / "store" / "candidates.csv").read_text(encoding="utf-8")
