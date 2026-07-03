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


def test_stage_basis_text_picks_latest_designated_round():
    from health_tech_research_agent import structured_evidence as se
    rounds = [{"series_designation": "series-a", "type": "series-a", "date": "2022-01", "is_priced_equity": True},
              {"series_designation": "series-b", "type": "series-b", "date": "2024-06", "is_priced_equity": True,
               "amount_usd_m": "50"}]
    assert se.stage_basis_text(rounds) == "Series B, $50, 2024-06"
    assert se.stage_basis_text([]) == ""                       # no dated round -> caller falls back to the label


def test_resolve_stage_basis_aligns_to_overridden_stage():
    from health_tech_research_agent import structured_evidence as se
    # signos-style: the data carries a later series-c round, but the human override locks the stage to series-b.
    rounds = [{"series_designation": "series-b", "type": "series-b", "date": "2021-03",
               "is_priced_equity": True, "amount_usd_m": "20"},
              {"series_designation": "series-c", "type": "series-c", "date": "2026-05", "is_priced_equity": True}]
    basis = se.resolve_stage_basis("signos", rounds, {}, "series-b")
    assert basis.startswith("Series B") and "Series C" not in basis   # never contradicts the resolved stage


def test_resolve_stage_basis_uses_funding_patch_for_equip():
    from health_tech_research_agent import structured_evidence as se
    # equip health: research stopped at series-b; the funding patch appends the real series-c the stage uses.
    rounds = [{"series_designation": "series-b", "type": "series-b", "date": "2021-05", "is_priced_equity": True}]
    assert se.resolve_stage_basis("equip health", rounds, {}, "series-c").startswith("Series C")


def test_resolve_stage_basis_shows_undisclosed_when_amount_missing():
    from health_tech_research_agent import structured_evidence as se
    # A placeholder amount ("unknown") and a missing amount field both render as "undisclosed $" (visible gap).
    placeholder = [{"series_designation": "series-b", "type": "series-b", "date": "2024-07",
                    "is_priced_equity": True, "amount": "unknown"}]
    absent = [{"series_designation": "series-b", "type": "series-b", "date": "2024-07", "is_priced_equity": True}]
    dollar_placeholder = [{"series_designation": "series-b", "type": "series-b", "date": "2024-07",
                           "is_priced_equity": True, "amount": "$unknown"}]   # value carries a leading $
    assert se.resolve_stage_basis("x", placeholder, {}, "series-b") == "Series B, undisclosed $, 2024-07"
    assert se.resolve_stage_basis("x", absent, {}, "series-b") == "Series B, undisclosed $, 2024-07"
    assert se.resolve_stage_basis("x", dollar_placeholder, {}, "series-b") == "Series B, undisclosed $, 2024-07"


def test_resolve_stage_basis_normal_company_matches_latest_round():
    from health_tech_research_agent import structured_evidence as se
    rounds = [{"series_designation": "series-b", "type": "series-b", "date": "2024-06",
               "is_priced_equity": True, "amount_usd_m": "50"}]
    assert se.resolve_stage_basis("acme", rounds, {}, "series-b") == "Series B, $50, 2024-06"


def test_resolve_stage_basis_falls_back_to_label_never_a_wrong_series():
    from health_tech_research_agent import structured_evidence as se
    rounds = [{"series_designation": "series-c", "type": "series-c", "date": "2026-01", "is_priced_equity": True}]
    assert se.resolve_stage_basis("x", rounds, {}, "series-b") == "Series B"   # label only, not the series-c round


def test_stage_basis_derived_from_fit_brief_rounds():
    import json
    rec = {"company": "grow", "business_model": "B2C", "funding_stage": "series-b", "background_fit": 8,
           "pmf": 10, "arr_level": 10, "growth": 9, "strain": 2, "final_score": 20, "path_passed": True,
           "agency_passed": True, "gate_floored": False, "floor_ok": True, "model_priority": "P0"}
    row = {"company": "grow", "fit_brief_json": json.dumps({"maturity_evidence": {"funding_rounds": [
        {"series_designation": "series-b", "type": "series-b", "date": "2025-11", "is_priced_equity": True,
         "amount_usd_m": "298"}], "ipo_event": {}}})}
    entry = ledger.build_entry(rec, row, batch_id="b", date_scored="2026-07-02", framework_version="v1.25")
    assert "Series B" in entry["stage_basis"] and "2025-11" in entry["stage_basis"]


def test_taxonomy_segment_extracted_and_rendered():
    import json
    from health_tech_research_agent import ledger
    rec = {"company": "acme", "business_model": "B2C", "funding_stage": "series-b", "background_fit": 8,
           "pmf": 9, "arr_level": 10, "growth": 9, "strain": 2, "final_score": 19, "path_passed": True,
           "agency_passed": True, "gate_floored": False, "floor_ok": True, "model_priority": "P0"}
    row = {"company": "acme", "fit_brief_json": json.dumps({"taxonomy_classification": {
        "primary_market_segment": "WOMENS_FAMILY_HEALTH", "subsegment_tags": ["maternity"],
        "product_model_tags": ["virtual_care"]}})}
    entry = ledger.build_entry(rec, row, batch_id="b", date_scored="2026-07-03", framework_version="v1.25")
    assert entry["taxonomy"]["segment"] == "WOMENS_FAMILY_HEALTH"
    assert entry["taxonomy"]["subsegment_tags"] == ["maternity"]
    assert ledger.render_summary_table([entry]).iloc[0]["Segment"] == "WOMENS_FAMILY_HEALTH"
    assert ledger.render_cards_csv([entry]).iloc[0]["Segment"] == "WOMENS_FAMILY_HEALTH"
    export = ledger.render_master_full_export([entry])
    assert export.iloc[0]["Segment"] == "WOMENS_FAMILY_HEALTH" and export.iloc[0]["Subsegment tags"] == "maternity"
