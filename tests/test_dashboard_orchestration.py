"""Phase 4 — orchestration: finalize_gate2_review_dir + build_dashboard end-to-end (durable artifacts,
user-store round-trip, §1a enforcement, segment-label degradation)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from health_tech_research_agent import dashboard, ledger, storage

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


def _gate2_dir(tmp_path, *, finalized=True):
    """A gate-2 out_dir holding ledger.jsonl (optionally finalized/reviewed), like the Colab OUT dir."""
    out = tmp_path / "gate2"
    out.mkdir()
    ledger.write_ledger(out / "ledger.jsonl", ledger.read_ledger(FIXTURE))
    if finalized:
        ledger.finalize_gate2_review_dir(out, reviewed_date="2026-07-03", reviewed_at_gate="gate2_sample")
    return out


def _research():
    return [{"company": "alpha health",
             "fit_brief_json": json.dumps({"commercial_evidence": {"revenue_or_arr": "$80M ARR"}}),
             "funding_finding": "Series B $50M (2024)."}]


# --- finalize_gate2_review_dir ----------------------------------------------

def test_finalize_dir_stamps_and_reads_back(tmp_path):
    out = _gate2_dir(tmp_path, finalized=False)
    result = ledger.finalize_gate2_review_dir(out, reviewed_date="2026-07-03", reviewed_at_gate="gate2_sample")
    assert result["stamped"] == 5 and result["readback_ok"] is True
    assert all(ledger.is_reviewed(e) for e in ledger.read_ledger(out / "ledger.jsonl"))


# --- §1a enforcement --------------------------------------------------------

def test_build_dashboard_refuses_unfinalized_ledger(tmp_path):
    out = _gate2_dir(tmp_path, finalized=False)
    with pytest.raises(dashboard.DashboardError) as exc:
        dashboard.build_dashboard(out / "ledger.jsonl", out_dir=tmp_path / "dash")
    assert "GATE-2 invariant" in str(exc.value)


# --- end-to-end -------------------------------------------------------------

def test_build_dashboard_writes_all_artifacts(tmp_path):
    out = _gate2_dir(tmp_path)
    dash_out = tmp_path / "dash"
    result = dashboard.build_dashboard(out / "ledger.jsonl", research=_research(), out_dir=dash_out)

    assert result.entries == 5
    assert result.readback_ok is True
    for name in ["all_companies.csv", "pursuit.csv", "contacts.csv", "segment_radar.csv",
                 "dashboard.html", "dashboard_records.json", "dashboard_user_store.xlsx"]:
        assert (dash_out / name).exists(), name
    assert result.tally.get("P0") == 1 and result.tally.get("P1") == 1
    assert result.report == {"orphaned_workspace": [], "orphaned_contacts": [], "changed": []}
    assert result.segment_labels_resolved is True     # repo taxonomy reachable in the test env


def test_research_accepts_a_csv_path(tmp_path):
    out = _gate2_dir(tmp_path)
    research_csv = tmp_path / "research.csv"
    pd.DataFrame(_research()).to_csv(research_csv, index=False)
    result = dashboard.build_dashboard(out / "ledger.jsonl", research=research_csv, out_dir=tmp_path / "dash")
    records = json.loads((Path(result.out_dir) / "dashboard_records.json").read_text())["records"]
    alpha = next(r for r in records if r["company"] == "alpha health")
    assert alpha["research"]["commercial"]["revenue_or_arr"] == "$80M ARR"


# --- user-store round-trip --------------------------------------------------

def _seed_user_store(path):
    workspace = pd.DataFrame([
        {"company": "beta health", "pursue": "TRUE", "status": "Seeking warm intro", "next_step": "ask Dana",
         "HQ": "NYC", "desirability_notes": "elite ARR", "deep_dive_notes": "", "last_updated": "",
         "last_seen_priority": "P3", "last_seen_segment": "Metabolic, nutrition & weight health"},
    ])
    contacts = pd.DataFrame([{"company": "beta health", "contact": "Dana Rivera", "title": "Head of Growth"}])
    storage.atomic_write_workbook(path, {"Workspace": workspace, "Contacts": contacts})


def test_build_dashboard_merges_and_persists_user_layer(tmp_path):
    out = _gate2_dir(tmp_path)
    dash_out = tmp_path / "dash"
    dash_out.mkdir()
    store = dash_out / "dashboard_user_store.xlsx"
    _seed_user_store(store)

    result = dashboard.build_dashboard(out / "ledger.jsonl", research=_research(), out_dir=dash_out)

    # pursuit view reflects the pursued company + the change ("was P3" -> now P1)
    pursuit = pd.read_csv(dash_out / "pursuit.csv").fillna("")
    beta = pursuit[pursuit["company"] == "beta health"].iloc[0]
    assert beta["status"] == "Seeking warm intro"
    assert beta["changed"] == "priority P3→P1"
    assert {"company": "beta health", "priority": {"from": "P3", "to": "P1"}} in result.report["changed"]

    # the written-back workbook keeps her notes and refreshes the snapshot to the current tier
    sheets = storage.load_workbook_sheets(store)
    ws = sheets["Workspace"].fillna("")
    beta_row = ws[ws["company"] == "beta health"].iloc[0]
    assert dashboard._truthy(beta_row["pursue"])       # xlsx may coerce "TRUE"->True; merge reads it either way
    assert beta_row["status"] == "Seeking warm intro"
    assert str(beta_row["last_seen_priority"]) == "P1"        # snapshot moved forward -> no false "changed" next run
    assert set(ws["company"]) == {"alpha health", "beta health", "gamma health", "delta health", "epsilon health"}


def test_second_run_is_stable_no_false_change(tmp_path):
    """After a run refreshes the snapshot, an unchanged re-run reports no change (idempotent-ish)."""
    out = _gate2_dir(tmp_path)
    dash_out = tmp_path / "dash"
    dash_out.mkdir()
    _seed_user_store(dash_out / "dashboard_user_store.xlsx")
    dashboard.build_dashboard(out / "ledger.jsonl", research=_research(), out_dir=dash_out)   # refreshes snapshot
    result2 = dashboard.build_dashboard(out / "ledger.jsonl", research=_research(), out_dir=dash_out)
    assert result2.report["changed"] == []       # snapshot now matches -> no phantom change


# --- segment-label degradation ----------------------------------------------

def test_segment_labels_degrade_to_codes_without_taxonomy(tmp_path):
    out = _gate2_dir(tmp_path)
    result = dashboard.build_dashboard(out / "ledger.jsonl", out_dir=tmp_path / "dash",
                                       taxonomy_dir=tmp_path / "no_taxonomy_here")
    assert result.segment_labels_resolved is False
    radar = pd.read_csv(Path(result.out_dir) / "segment_radar.csv")
    assert "METABOLIC_NUTRITION_HEALTH" in set(radar["segment"])   # code used as the label
