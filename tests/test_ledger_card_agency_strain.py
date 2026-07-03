"""Card render additions (2026-07-03): the Agency (gate + reset) column and the Strain logic, plus the
apply_gate2_decisions orchestrator (merge priority overrides into an existing ledger + re-render)."""

from __future__ import annotations

import pandas as pd

from health_tech_research_agent import ledger
from health_tech_research_agent import storage


def _rec(company, **over):
    base = dict(company=company, business_model="B2B2C", funding_stage="series-b",
                background_fit=8, pmf=9, arr_level=10, growth=9, strain=2, final_score=19,
                path_passed=True, agency_passed=True, gate_floored=False, floor_ok=True,
                model_priority="P0", human_override=None, floored_on_bg=False, tier_review=False,
                floor_reason="", data_feedback_loop="yes", background_fit_basis="loop",
                growth_note="high", growth_evidence="+120%", strain_strength="STRONG",
                strain_rationale="a2=72", path_detail="alive", agency_detail="series-b in-window",
                reset_detail="reset events [none]; none fired", revenue_or_arr="$80M ARR")
    base.update(over)
    return base


def _entry(rec):
    return ledger.build_entry(rec, batch_id="b03", date_scored="2026-07-03", framework_version="v1.25")


def test_card_has_agency_column_showing_reset():
    # grow-style: series-d-plus that passed agency via a reset — the card must show WHY it wasn't floored.
    rec = _rec("grow therapy", funding_stage="series-d-plus", agency_detail="series-d-plus late-stage +reset",
               reset_detail="reset events [leadership-change, strategic-pivot]; fired")
    row = ledger.render_cards_csv([_entry(rec)]).iloc[0]
    assert "Agency" in ledger.CARDS_CONTEXT_COLUMNS
    assert row["Agency"].startswith("Pass") and "reset" in row["Agency"].lower()
    assert "leadership-change" in row["Agency"]


def test_card_agency_shows_floored():
    rec = _rec("oura", funding_stage="series-d-plus", agency_passed=False, gate_floored=True, floor_ok=False,
               model_priority="P3", agency_detail="series-d-plus late-stage (no reset)",
               reset_detail="reset events [none]; none fired")
    row = ledger.render_cards_csv([_entry(rec)]).iloc[0]
    assert row["Agency"].startswith("Floored") and "series-d-plus" in row["Agency"]


def test_card_strain_shows_logic_not_just_a2():
    row = ledger.render_cards_csv([_entry(_rec("x", strain_strength="STRONG", strain_rationale="a2=72"))]).iloc[0]
    assert "STRONG" in row["Strain rationale"] and "72" in row["Strain rationale"]
    weak = ledger.render_cards_csv([_entry(_rec("y", strain=0, strain_strength="WEAK",
                                                strain_rationale="default-low"))]).iloc[0]
    assert "WEAK" in weak["Strain rationale"]


def test_apply_gate2_decisions_merges_and_rerenders(tmp_path):
    roster = [_rec("grow therapy"),
              _rec("function health", business_model="B2C", background_fit=4, floor_ok=False,
                   model_priority="P3", final_score=15)]
    research = pd.DataFrame([{"company": "grow therapy", "funding_finding": "x"},
                             {"company": "function health", "funding_finding": "y"}])
    ledger.build_gate2_artifacts(roster, research, batch_id="b03", date_scored="2026-07-03", out_dir=tmp_path)

    result = ledger.apply_gate2_decisions(
        tmp_path, [{"company": "function health", "human_override": "P1", "override_reason": "unicorn"}],
        decided_date="2026-07-03", decided_at_gate="gate2_batch03", research=research)

    assert result["readback_ok"] is True and result["applied"] == 1
    reopened = ledger.read_ledger(tmp_path / "ledger.jsonl")
    fh = next(e for e in reopened if e["company"] == "function health")
    assert ledger.final_priority(fh) == "P1" and fh["decision"]["history"][-1]["to"] == "P1"
    # the re-rendered summary reflects the override
    summary = storage.load_csv(tmp_path / "summary_table.csv")
    assert summary[summary["Company"] == "function health"].iloc[0]["Tier"] == "P1"
