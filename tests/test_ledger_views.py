"""Rendered-view tests (Commit E) — summary_table (scan) + master_full_export (all fields + research join)."""

from __future__ import annotations

import pandas as pd

from health_tech_research_agent import ledger
from health_tech_research_agent import storage


def _entry(company, *, model="B2C", stage="series-b", **over):
    rec = dict(company=company, business_model=model, funding_stage=stage,
               background_fit=8, pmf=10, arr_level=10, growth=9, strain=2, final_score=20,
               path_passed=True, agency_passed=True, gate_floored=False, floor_ok=True,
               model_priority="P0", human_override=None, floored_on_bg=False, tier_review=False,
               floor_reason="", data_feedback_loop="yes", background_fit_basis="daily loop",
               growth_note="high(+120%)", growth_evidence="+120%", strain_strength="MODERATE",
               strain_rationale="scaling", path_detail="B2C alive", agency_detail="Series B in-window",
               reset_detail="none", revenue_or_arr="$80M ARR")
    rec.update(over)
    return ledger.build_entry(rec, batch_id="b03", date_scored="2026-07-02", framework_version="v1.25")


def _fh():
    return _entry("function health", background_fit=4, pmf=10, final_score=16, floor_ok=False,
                  model_priority="P3", human_override="P1", background_fit_basis="2x/yr episodic")


def _medically_home():
    return _entry("medically home", model="B2B", stage="series-c", background_fit=None, pmf=None,
                  arr_level=7, growth=5, final_score=None, path_passed=False, agency_passed=False,
                  gate_floored=True, floor_ok=False, model_priority="P3", background_fit_basis="")


def test_summary_table_columns_and_tier():
    df = ledger.render_summary_table([_entry("grow"), _fh()])
    assert list(df.columns) == ledger.SUMMARY_COLUMNS
    grow = df[df["Company"] == "grow"].iloc[0]
    assert grow["Tier"] == "P0" and grow["FINAL"] == 20 and grow["Key flag"] == "" and grow["Floor reason"] == ""
    fh = df[df["Company"] == "function health"].iloc[0]
    assert fh["Tier"] == "P3"                                   # derived from model until overridden
    assert fh["Key flag"] in {"low_score_floor", "override_candidate"}
    assert "Low score" in fh["Floor reason"]


def test_summary_floor_reason_distinguishes_gate_from_low_score():
    df = ledger.render_summary_table([_medically_home(), _fh()])
    mh = df[df["Company"] == "medically home"].iloc[0]
    fh = df[df["Company"] == "function health"].iloc[0]
    assert mh["Floor reason"].startswith("B2B floor")
    assert fh["Floor reason"].startswith("Low score")
    assert mh["Recommendation"] == "accept" and fh["Recommendation"] == "review_override"


def test_summary_tier_reflects_manual_override():
    entries = ledger.apply_decisions(
        [_fh()], [{"company": "function health", "human_override": "P1", "override_reason": "unicorn"}],
        decided_date="2026-07-02", decided_at_gate="gate2")
    df = ledger.render_summary_table(entries)
    assert df.iloc[0]["Tier"] == "P1"                           # override wins in the scan too


def test_master_export_has_display_labels_and_derived_fields():
    df = ledger.render_master_full_export([_entry("grow")])
    for header in ("Background Fit", "Product Market Fit", "ARR", "Growth", "Strain", "FINAL",
                   "Final priority", "Provenance", "Human override", "Decision history"):
        assert header in df.columns
    row = df.iloc[0]
    assert row["Background Fit"] == 8 and row["Product Market Fit"] == 10
    assert row["Final priority"] == "P0" and row["Provenance"] == "model-accepted"


def test_master_export_joins_research_by_company():
    research = [
        {"company": "function health", "funding_finding": "Series B $298M", "growth_finding": "+450% YoY"},
        {"company": "ghost co", "funding_finding": "ignored — not in ledger"},
    ]
    df = ledger.render_master_full_export([_fh(), _entry("grow")], research=research)
    fh = df[df["Company"] == "function health"].iloc[0]
    grow = df[df["Company"] == "grow"].iloc[0]
    assert fh["funding_finding"] == "Series B $298M" and fh["growth_finding"] == "+450% YoY"
    assert grow["funding_finding"] in ("", None) or pd.isna(grow["funding_finding"])   # no research row -> blank
    assert "ghost co" not in set(df["Company"])                # research for a non-ledger company is ignored


def test_master_export_accepts_research_dataframe():
    research = pd.DataFrame([{"company": "grow", "commercial_scale_finding": "named customers"}])
    df = ledger.render_master_full_export([_entry("grow")], research=research)
    assert df.iloc[0]["commercial_scale_finding"] == "named customers"


def test_write_views_round_trip_to_csv(tmp_path):
    entries = [_entry("grow"), _fh()]
    summary_path = ledger.write_summary_table(tmp_path / "summary_table.csv", entries)
    export_path = ledger.write_master_full_export(tmp_path / "master_full_export.csv", entries,
                                                  research=[{"company": "grow", "funding_finding": "Seed+A+B"}])
    summary = storage.load_csv(summary_path)
    export = storage.load_csv(export_path)
    assert set(summary["Company"]) == {"grow", "function health"}
    assert export[export["Company"] == "grow"].iloc[0]["funding_finding"] == "Seed+A+B"


def test_empty_entries_render_empty_frames():
    assert list(ledger.render_summary_table([]).columns) == ledger.SUMMARY_COLUMNS
    assert ledger.render_master_full_export([]).empty
