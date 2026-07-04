"""Phase-1 Step 1 — the hosted-dashboard web shell: auth gate + serving the render.

Runs offline against the bundled sample-ledger fixture (no Google). Skips cleanly if the `web` extra
(FastAPI) isn't installed, so the base suite still runs without it.
"""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")  # webapp tests require the `web` extra

from fastapi.testclient import TestClient  # noqa: E402

from health_tech_research_agent.webapp.app import create_app  # noqa: E402
from health_tech_research_agent.webapp.config import WebConfig  # noqa: E402
from health_tech_research_agent.webapp.security import hash_password, verify_password  # noqa: E402
from health_tech_research_agent.webapp.source import FixtureDashboardSource  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def client() -> TestClient:
    config = WebConfig(session_secret="test-secret-not-real", password_hash=hash_password(PASSWORD))
    return TestClient(create_app(config, FixtureDashboardSource(FIXTURE)))


def test_healthz_is_open() -> None:
    config = WebConfig(session_secret="s", password_hash=hash_password("x"))
    r = TestClient(create_app(config, FixtureDashboardSource(FIXTURE))).get("/healthz")
    assert r.status_code == 200 and "ok" in r.text


def test_home_requires_login(client: TestClient) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_page_renders(client: TestClient) -> None:
    r = client.get("/login")
    assert r.status_code == 200
    assert "Sign in" in r.text and 'name="password"' in r.text


def test_wrong_password_rejected_and_no_session(client: TestClient) -> None:
    r = client.post("/login", data={"password": "nope"}, follow_redirects=False)
    assert r.status_code == 401
    assert "Incorrect password." in r.text
    # still not authenticated
    assert client.get("/", follow_redirects=False).status_code == 303


def test_login_then_home_renders_dashboard(client: TestClient) -> None:
    r = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    home = client.get("/")
    assert home.status_code == 200
    assert "alpha health" in home.text                 # rendered from the fixture ledger
    assert "&#8635; Refresh" in home.text and "Log out" in home.text  # control bar injected


def test_refresh_requires_login(client: TestClient) -> None:
    r = client.post("/refresh", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_refresh_when_authed_rebuilds_and_redirects(client: TestClient) -> None:
    client.post("/login", data={"password": PASSWORD})
    r = client.post("/refresh", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "alpha health" in client.get("/").text


def test_logout_clears_session(client: TestClient) -> None:
    client.post("/login", data={"password": PASSWORD})
    assert client.get("/", follow_redirects=False).status_code == 200
    client.post("/logout", follow_redirects=False)
    assert client.get("/", follow_redirects=False).status_code == 303


def test_security_hash_roundtrip() -> None:
    h = hash_password("s3cret-pw")
    assert verify_password("s3cret-pw", h)
    assert not verify_password("wrong", h)
    assert not verify_password("s3cret-pw", "not-a-valid-hash")
