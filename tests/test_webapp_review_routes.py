"""Phase-2 Step 3 — the in-app GATE-2 review routes (TestClient over the fixture review source)."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from health_tech_research_agent import ledger  # noqa: E402
from health_tech_research_agent.webapp.app import create_app  # noqa: E402
from health_tech_research_agent.webapp.config import WebConfig  # noqa: E402
from health_tech_research_agent.webapp.security import hash_password  # noqa: E402
from health_tech_research_agent.webapp.source import FixtureDashboardSource  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"
PASSWORD = "review-pw"


def _client(tmp_path, *, login=True):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path)
    config = WebConfig(session_secret="s", password_hash=hash_password(PASSWORD))
    client = TestClient(create_app(config, src))
    if login:
        client.post("/login", data={"password": PASSWORD})
    return client, src


def test_review_requires_login(tmp_path):
    client, _ = _client(tmp_path, login=False)
    r = client.get("/review", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_review_index_lists_pending(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/review")
    assert r.status_code == 200
    assert "GATE-2 Review" in r.text and "alpha health" in r.text
    assert "/review/finalize" in r.text


def test_review_card_renders_detail_plus_control(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/review/alpha health")
    assert r.status_code == 200
    assert "SCORING &amp; DECISION" in r.text            # reused dashboard detail body
    assert "Your decision — priority only" in r.text


def test_decision_override_saves_to_the_store(tmp_path):
    client, src = _client(tmp_path)
    r = client.post("/review/decision",
                    data={"company": "alpha health", "action": "P1", "reason": "stronger than model"},
                    follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/review"
    entries, _ = src.read_review_data()
    alpha = {e["company"].lower(): e for e in entries}["alpha health"]
    assert alpha["decision"]["human_override"] == "P1"
    assert alpha["decision"]["override_reason"] == "stronger than model"


def test_bad_action_is_rejected(tmp_path):
    client, _ = _client(tmp_path)
    r = client.post("/review/decision", data={"company": "alpha health", "action": "BOGUS"})
    assert r.status_code == 400


def test_finalize_stamps_all_and_redirects_to_dashboard(tmp_path):
    client, src = _client(tmp_path)
    r = client.post("/review/finalize", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    entries, _ = src.read_review_data()
    assert all(ledger.is_reviewed(e) for e in entries)   # every entry now finalized
