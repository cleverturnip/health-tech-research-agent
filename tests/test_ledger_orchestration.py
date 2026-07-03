"""Orchestration test (Commit F) — build_gate2_artifacts: scored roster -> ledger.jsonl + three CSV views."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from health_tech_research_agent import ledger
from health_tech_research_agent import storage


def _rec(company, **over):
    base = dict(company=company, business_model="B2C", funding_stage="series-b",
                background_fit=8, pmf=10, arr_level=10, growth=9, strain=2, final_score=20,
                path_passed=True, agency_passed=True, gate_floored=False, floor_ok=True,
                model_priority="P0", human_override=None, floored_on_bg=False, tier_review=False,
                floor_reason="", data_feedback_loop="yes", background_fit_basis="loop",
                growth_note="high(+120%)", growth_evidence="+120%", strain_strength="MODERATE",
                strain_rationale="scaling", path_detail="alive", agency_detail="in-window",
                reset_detail="none", revenue_or_arr="$80M ARR")
    base.update(over)
    return base


def test_build_gate2_artifacts_writes_all_four_and_joins_research(tmp_path):
    roster = [_rec("grow"),
              _rec("function health", background_fit=4, floor_ok=False, model_priority="P3", human_override="P1")]
    research = pd.DataFrame([
        {"company": "grow", "funding_finding": "Seed+A+B", "fit_brief_json": '{"x": 1}'},
        {"company": "function health", "funding_finding": "Series B $298M", "fit_brief_json": '{"y": 2}'},
    ])

    result = ledger.build_gate2_artifacts(
        roster, research, batch_id="b03", date_scored="2026-07-02", out_dir=tmp_path,
        framework_version="v1.25")

    assert result.entries == 2 and result.readback_ok is True
    assert result.tally == {"P0": 1, "P3": 1}                       # function health P3 by model (override not pre-applied)
    for path in (result.ledger_path, result.summary_path, result.cards_path, result.export_path):
        assert Path(path).exists()

    reopened = ledger.read_ledger(result.ledger_path)
    assert {e["company"] for e in reopened} == {"grow", "function health"}

    export = storage.load_csv(result.export_path)
    assert "fit_brief_json" not in export.columns                   # machine JSON dropped from the human export
    assert export[export["Company"] == "grow"].iloc[0]["funding_finding"] == "Seed+A+B"

    summary = storage.load_csv(result.summary_path)
    assert set(summary["Company"]) == {"grow", "function health"}

    cards = storage.load_csv(result.cards_path)
    assert set(ledger.CARDS_DECISION_COLUMNS).issubset(cards.columns)


def test_build_gate2_artifacts_accepts_list_research_and_default_version(tmp_path):
    roster = [_rec("grow")]
    result = ledger.build_gate2_artifacts(
        roster, [{"company": "grow", "funding_finding": "Seed"}],
        batch_id="b03", date_scored="2026-07-02", out_dir=tmp_path)   # framework_version defaults to the SOT
    reopened = ledger.read_ledger(result.ledger_path)
    assert reopened[0]["framework_version"].startswith("v")
    export = storage.load_csv(result.export_path)
    assert export.iloc[0]["funding_finding"] == "Seed"
