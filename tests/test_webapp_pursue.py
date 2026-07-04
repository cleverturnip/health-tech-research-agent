"""Phase-1 in-app pursue editing (2026-07-04): the targeted Sheet cell write + the /pursue endpoint.

Offline: `dashboard_gsheet.set_pursue` is exercised against a fake worksheet; the endpoint against a fake
editable source. The live Sheet write is proven at live verification (needs the service account with Editor).
"""

import types
from pathlib import Path

import pytest

from health_tech_research_agent import dashboard_gsheet as gs

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from health_tech_research_agent.webapp.app import create_app  # noqa: E402
from health_tech_research_agent.webapp.config import WebConfig  # noqa: E402
from health_tech_research_agent.webapp.security import hash_password  # noqa: E402
from health_tech_research_agent.webapp.source import FixtureDashboardSource  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"
PASSWORD = "pw-for-tests"


# --- the Sheet cell write ---------------------------------------------------

class _FakeWS:
    def __init__(self, header, rows):
        self.header = list(header)
        self.rows = [list(r) for r in rows]
        self.appended = []

    def row_values(self, n):
        return list(self.header) if n == 1 else list(self.rows[n - 2])

    def col_values(self, c):
        return [self.header[c - 1]] + [r[c - 1] for r in self.rows]

    def update_cell(self, r, c, val):
        self.rows[r - 2][c - 1] = val

    def append_row(self, row):
        self.rows.append(list(row))
        self.appended.append(list(row))

    def cell(self, r, c):
        return types.SimpleNamespace(value=self.rows[r - 2][c - 1])


class _FakeSS:
    def __init__(self, ws):
        self._ws = ws

    def worksheet(self, title):
        assert title == gs.dash.WORKSPACE_SHEET
        return self._ws


def test_set_pursue_true_writes_cell_and_reads_back():
    ws = _FakeWS(["company", "pursue", "status"], [["zoe", "", ""], ["nourish", "", ""]])
    assert gs.set_pursue(_FakeSS(ws), "Zoe", True) is True   # case-insensitive match
    assert ws.rows[0][1] == "TRUE"
    assert ws.rows[1][1] == ""                                # other rows untouched


def test_set_pursue_false_clears_cell():
    ws = _FakeWS(["company", "pursue"], [["zoe", "TRUE"]])
    assert gs.set_pursue(_FakeSS(ws), "zoe", False) is True
    assert ws.rows[0][1] == ""


def test_set_pursue_unknown_company_appends_row():
    ws = _FakeWS(["company", "pursue"], [["zoe", ""]])
    assert gs.set_pursue(_FakeSS(ws), "newco", True) is True
    assert ws.appended and ws.appended[0][0] == "newco" and ws.appended[0][1] == "TRUE"


def test_set_pursue_missing_columns_raises():
    ws = _FakeWS(["name", "flag"], [["zoe", ""]])
    with pytest.raises(KeyError):
        gs.set_pursue(_FakeSS(ws), "zoe", True)


# --- the endpoint -----------------------------------------------------------

class _EditableSource(FixtureDashboardSource):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.calls = []
        self.ret = True

    def set_pursue(self, company, pursue):
        self.calls.append((company, pursue))
        return self.ret


def _client(source):
    config = WebConfig(session_secret="s", password_hash=hash_password(PASSWORD))
    c = TestClient(create_app(config, source))
    return c


def test_home_injects_pursue_js_when_editable():
    src = _EditableSource(FIXTURE)
    c = _client(src)
    c.post("/login", data={"password": PASSWORD})
    assert "fetch('/pursue'" in c.get("/").text


def test_home_no_pursue_js_for_readonly_demo():
    c = _client(FixtureDashboardSource(FIXTURE))
    c.post("/login", data={"password": PASSWORD})
    assert "fetch('/pursue'" not in c.get("/").text


def test_pursue_requires_login():
    c = _client(_EditableSource(FIXTURE))
    r = c.post("/pursue", json={"company": "zoe", "pursue": True})
    assert r.status_code == 401


def test_pursue_success_calls_source():
    src = _EditableSource(FIXTURE)
    c = _client(src)
    c.post("/login", data={"password": PASSWORD})
    r = c.post("/pursue", json={"company": "zoe", "pursue": True})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert src.calls == [("zoe", True)]


def test_pursue_readback_failure_is_500():
    src = _EditableSource(FIXTURE)
    src.ret = False
    c = _client(src)
    c.post("/login", data={"password": PASSWORD})
    r = c.post("/pursue", json={"company": "zoe", "pursue": True})
    assert r.status_code == 500


def test_pursue_not_available_on_demo_source_is_400():
    c = _client(FixtureDashboardSource(FIXTURE))
    c.post("/login", data={"password": PASSWORD})
    r = c.post("/pursue", json={"company": "zoe", "pursue": True})
    assert r.status_code == 400
