"""Phase-3 GATE-1 Step 3 — the /discover routes (TestClient over the fixture source, fake OpenAI client)."""

import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from health_tech_research_agent.webapp.app import create_app  # noqa: E402
from health_tech_research_agent.webapp.config import WebConfig  # noqa: E402
from health_tech_research_agent.webapp.security import hash_password  # noqa: E402
from health_tech_research_agent.webapp.source import FixtureDashboardSource  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"
PASSWORD = "discover-pw"


class _FakeResponses:
    def __init__(self, text, calls):
        self._text, self._calls = text, calls

    def create(self, **kwargs):
        self._calls.append(kwargs)
        return types.SimpleNamespace(output_text=self._text)


class _FakeClient:
    def __init__(self, text):
        self.calls = []
        self.responses = _FakeResponses(text, self.calls)


class _DiscoverSource(FixtureDashboardSource):
    """Fixture source with a canned OpenAI client, so the discovery route runs fully offline."""

    def __init__(self, *args, reply="", **kwargs):
        super().__init__(*args, **kwargs)
        self.fake = _FakeClient(reply)

    def openai_client(self):
        return self.fake


def _client(tmp_path, *, login=True, reply=""):
    src = _DiscoverSource(FIXTURE, review_work_dir=tmp_path, reply=reply)
    config = WebConfig(session_secret="s", password_hash=hash_password(PASSWORD))
    client = TestClient(create_app(config, src))
    if login:
        client.post("/login", data={"password": PASSWORD})
    return client, src


def test_discover_requires_login(tmp_path):
    client, _ = _client(tmp_path, login=False)
    r = client.get("/discover", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_discover_page_renders(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/discover")
    assert r.status_code == 200
    assert "Company Discovery" in r.text          # nav tab (chrome injected)
    assert "Your target market (thesis)" in r.text and 'id="chat"' in r.text


def test_thesis_saves_and_reloads(tmp_path):
    client, src = _client(tmp_path)
    r = client.post("/discover/thesis", data={"thesis": "early-stage metabolic health"},
                    follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/discover"
    assert src.read_thesis() == "early-stage metabolic health"
    assert "early-stage metabolic health" in client.get("/discover").text   # prefilled on reload


def test_message_returns_reply_and_candidates(tmp_path):
    reply = ('Here are a few.\n```candidates\n'
             '[{"company":"Acme Health","why":"daily engagement","signal":"Series A, $14M"}]\n```')
    client, src = _client(tmp_path, reply=reply)
    r = client.post("/discover/message",
                    json={"conversation": [{"role": "user", "content": "metabolic health, early stage"}]})
    assert r.status_code == 200
    data = r.json()
    assert data["reply"] == "Here are a few."
    assert data["candidates"] == [{"company": "Acme Health", "why": "daily engagement", "signal": "Series A, $14M"}]
    # the grounded system prompt + web search were passed through
    call = src.fake.calls[0]
    assert call["tools"] == [{"type": "web_search"}]
    assert "researched" not in call["input"][0]["content"]   # roster grounding is in instructions, not user input
    assert "USE WEB SEARCH" in call["instructions"]


def test_message_drops_already_researched_candidates(tmp_path):
    # The fixture ledger has "alpha health"; the model re-proposes "Alpha" (+ a genuinely-new one).
    reply = ('Two ideas.\n```candidates\n'
             '[{"company":"Alpha","why":"w","signal":"s"},{"company":"Brand New Co","why":"w2","signal":"s2"}]\n```')
    client, _ = _client(tmp_path, reply=reply)
    r = client.post("/discover/message",
                    json={"conversation": [{"role": "user", "content": "mental health"}]})
    data = r.json()
    assert [c["company"] for c in data["candidates"]] == ["Brand New Co"]   # Alpha filtered out
    assert "already-researched" in data["reply"] and "Alpha" in data["reply"]


def test_message_empty_conversation_rejected(tmp_path):
    client, _ = _client(tmp_path)
    r = client.post("/discover/message", json={"conversation": [{"role": "user", "content": "   "}]})
    assert r.status_code == 400


def test_approve_writes_candidate_csv(tmp_path):
    client, src = _client(tmp_path)
    r = client.post("/discover/approve", json={"candidates": [
        {"company": "Acme Health", "why": "daily engagement", "signal": "Series A"},
        {"company": "", "why": "dropped", "signal": "x"},   # blank company skipped
    ]})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] and data["count"] == 1
    saved = (tmp_path / data["filename"]).read_text(encoding="utf-8")
    assert "Acme Health" in saved and "dropped" not in saved


def test_approve_no_candidates_rejected(tmp_path):
    client, _ = _client(tmp_path)
    r = client.post("/discover/approve", json={"candidates": []})
    assert r.status_code == 400
