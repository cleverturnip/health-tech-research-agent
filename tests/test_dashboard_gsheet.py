"""The Google-Sheet store adapter (reliable editable surface) — tested against a duck-typed fake gspread
Spreadsheet, so no live API is needed. Contract: input-only (never overwrites an existing tab), seeds once."""

from pathlib import Path

import pandas as pd

from health_tech_research_agent import dashboard, dashboard_gsheet, ledger

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


class FakeWS:
    def __init__(self, title, records=None):
        self.title = title
        self._records = records or []
        self.written = None                 # set by update() — None means "never written" (input-only proof)

    def get_all_records(self):
        return list(self._records)

    def update(self, values):
        self.written = values


class FakeSheet:
    def __init__(self, worksheets=None, url="https://docs.google.com/spreadsheets/d/FAKE"):
        self._ws = {w.title: w for w in (worksheets or [])}
        self.url = url

    def worksheets(self):
        return list(self._ws.values())

    def worksheet(self, title):
        if title not in self._ws:
            raise KeyError(title)
        return self._ws[title]

    def add_worksheet(self, title, rows, cols):
        ws = FakeWS(title)
        self._ws[title] = ws
        return ws


def _records():
    entries = ledger.finalize_gate2_review(
        ledger.read_ledger(FIXTURE), reviewed_date="2026-07-03", reviewed_at_gate="g")
    return dashboard.build_company_records(entries)


def _gate2(tmp_path):
    out = tmp_path / "gate2"
    out.mkdir()
    ledger.write_ledger(out / "ledger.jsonl", ledger.read_ledger(FIXTURE))
    ledger.finalize_gate2_review_dir(out, reviewed_date="2026-07-03", reviewed_at_gate="g")
    return out


# --- adapter ----------------------------------------------------------------

def test_read_empty_store():
    sh = FakeSheet()
    assert dashboard_gsheet.read_gsheet_store(sh) == ([], [])
    assert dashboard_gsheet.store_has_workspace(sh) is False


def test_seed_creates_both_tabs_with_all_companies():
    sh = FakeSheet()
    assert dashboard_gsheet.seed_gsheet_store(sh, _records()) is True
    assert dashboard_gsheet.store_has_workspace(sh) is True
    ws = sh.worksheet("Workspace")
    assert ws.written[0][:2] == ["company", "pursue"]      # header
    assert len(ws.written) == 1 + 5                        # header + one row per company
    assert "Contacts" in {w.title for w in sh.worksheets()}


def test_seed_is_input_only_never_touches_existing_tab():
    existing = FakeWS("Workspace", records=[{"company": "beta health", "pursue": "TRUE", "status": "note"}])
    sh = FakeSheet([existing])
    dashboard_gsheet.seed_gsheet_store(sh, _records())
    assert existing.written is None                         # existing Workspace never overwritten
    assert "Contacts" in {w.title for w in sh.worksheets()}  # missing tab still gets seeded


# --- build_dashboard with a gsheet handle -----------------------------------

def test_build_dashboard_gsheet_seeds_on_first_run(tmp_path):
    sh = FakeSheet()
    out = _gate2(tmp_path)
    res = dashboard.build_dashboard(out / "ledger.jsonl", out_dir=tmp_path / "dash", gsheet=sh)
    assert res.store_seeded is True
    assert res.user_store_path == sh.url
    assert dashboard_gsheet.store_has_workspace(sh)
    assert (Path(res.out_dir) / "dashboard.html").exists()


def test_build_dashboard_gsheet_reads_edits_without_touching_the_sheet(tmp_path):
    edited = FakeWS("Workspace", records=[{"company": "beta health", "pursue": "TRUE",
                                           "status": "Seeking warm intro"}])
    contacts = FakeWS("Contacts", records=[])
    sh = FakeSheet([edited, contacts])
    out = _gate2(tmp_path)
    res = dashboard.build_dashboard(out / "ledger.jsonl", out_dir=tmp_path / "dash", gsheet=sh)

    assert res.store_seeded is False
    assert edited.written is None            # INPUT-ONLY: your edited tab is never overwritten
    pursuit = pd.read_csv(Path(res.out_dir) / "pursuit.csv").fillna("")
    assert pursuit[pursuit["company"] == "beta health"].iloc[0]["status"] == "Seeking warm intro"
