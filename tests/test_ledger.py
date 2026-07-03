"""Ledger entry-builder tests (MASTER_REDESIGN_SPEC §3.4 / §4).

Synthetic `score_company`-shaped records exercise `build_entry` + routing + derived-on-read, decoupled from
the live scorer. One integration test asserts the 2026-07-02 rationale passthrough is present on real
`score_company` output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from health_tech_research_agent import ledger
from health_tech_research_agent import structured_evidence as se


BATCH = "batch_test_2026-07-02"
DATE = "2026-07-02"


def _rec(**over):
    """A floor-PASS P0 baseline score_company record; override fields per test."""
    base = dict(
        company="grow therapy", business_model="B2B2C", funding_stage="series-c",
        background_fit=8, pmf=10, arr_level=10, growth=9, strain=2, final_score=20,
        path_passed=True, agency_passed=True, gate_floored=False, floor_ok=True,
        model_priority="P0", human_override=None, final_priority="P0",
        tier_review=False, floored_on_bg=False, floor_reason="", layer="threshold",
        data_feedback_loop="yes", background_fit_basis="frequent engagement + data loop",
        growth_band="high", growth_basis="revenue-rate", growth_note="high(+120% YoY)",
        growth_evidence="+120% YoY", strain_strength="MODERATE", strain_rationale="fast scale",
        path_detail="B2B2C — institutional channel present", agency_detail="Series C → in-window",
        reset_detail="reset events [none]; none fired", business_model_needs_review=False,
        revenue_or_arr="$80M ARR",
    )
    base.update(over)
    return base


def test_framework_version_from_sot_fixture(tmp_path):
    sot = tmp_path / "SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md"
    sot.write_text("# header\n**FRAMEWORK_VERSION: v9.42 (2026-07-02)**\n", encoding="utf-8")
    assert ledger.read_framework_version(sot) == "v9.42"


def test_framework_version_default_reads_real_sot():
    version = ledger.read_framework_version()
    assert version.startswith("v") and version[1].isdigit()


def test_framework_version_missing_raises(tmp_path):
    empty = tmp_path / "sot.md"
    empty.write_text("no version here\n", encoding="utf-8")
    with pytest.raises(ledger.LedgerError):
        ledger.read_framework_version(empty)


def test_entry_stamps_framework_version_and_empty_decision():
    entry = ledger.build_entry(_rec(), batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert entry["framework_version"] == "v1.25"
    assert entry["batch_id"] == BATCH and entry["date_scored"] == DATE
    assert entry["decision"] == {
        "human_override": None, "override_reason": None, "taxonomy_override": None,
        "taxonomy_override_reason": None, "decided_date": None, "decided_at_gate": None, "history": [],
    }


def test_scoring_block_faithful_and_pmf_breakout():
    entry = ledger.build_entry(_rec(), batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    s = entry["scoring"]
    assert s["bg_fit"] == {"score": 8, "loop": True, "rationale": "frequent engagement + data loop"}
    assert s["pmf"]["score"] == 10
    assert s["pmf"]["arr_level"]["score"] == 10 and "$80M ARR" in s["pmf"]["arr_level"]["basis"]
    assert s["pmf"]["growth"]["score"] == 9 and s["pmf"]["growth"]["basis"] == "high(+120% YoY)"
    assert s["strain"] == {"score": 2, "strength": "MODERATE", "rationale": "fast scale"}
    assert s["final_score"] == 20 and s["floor_rule"]["passed"] is True


def test_clear_p0_accepts_and_is_not_override_candidate():
    entry = ledger.build_entry(_rec(), batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert entry["model_priority"] == "P0"
    assert entry["recommended_action"] == "accept"
    assert entry["override_candidate"] is False
    assert entry["flags"] == []
    assert ledger.final_priority(entry) == "P0"
    assert ledger.provenance(entry) == "model-accepted"


def test_documented_override_is_candidate_not_pre_applied():
    # Function Health: pure §B model_priority P3, documented override P1 -> override_candidate, decision EMPTY.
    rec = _rec(company="function health", business_model="B2C", funding_stage="series-b",
               background_fit=4, pmf=10, arr_level=10, growth=10, strain=2, final_score=16,
               floor_ok=False, model_priority="P3", human_override="P1", final_priority="P1",
               layer="override", data_feedback_loop="no",
               background_fit_basis="2x/yr lab — episodic", floor_reason="floor-rule — bg_fit=4 / pmf=10")
    entry = ledger.build_entry(rec, batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert entry["model_priority"] == "P3"
    assert entry["override_candidate"] is True
    assert entry["decision"]["human_override"] is None          # NOT pre-applied — Katelynd decides at the gate
    assert ledger.final_priority(entry) == "P3"                 # derived from model until she overrides
    assert entry["recommended_action"] == "review_override"
    types = {f["type"] for f in entry["flags"]}
    assert "override_candidate" in types and "low_score_floor" in types


def test_low_score_floor_flag_only_when_not_gate_floored():
    rec = _rec(background_fit=4, pmf=10, final_score=16, floor_ok=False, model_priority="P3")
    entry = ledger.build_entry(rec, batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert {f["type"] for f in entry["flags"]} == {"low_score_floor"}
    assert entry["scoring"]["floor_rule"]["passed"] is False
    assert "Background Fit 4 (≤ 4)" in entry["scoring"]["floor_rule"]["reason"]


def test_gate_floor_b2b_reads_distinct_from_low_score():
    # medically home: B2B gate floor; bg n/a (None). Distinct from a low-score floor.
    rec = _rec(company="medically home", business_model="B2B", funding_stage="series-c",
               background_fit=None, pmf=None, arr_level=7, growth=5, strain=1, final_score=None,
               path_passed=False, agency_passed=False, gate_floored=True, floor_ok=False,
               model_priority="P3", floor_reason="PATH Test A: B2B floor — human-locked floor list",
               data_feedback_loop="", background_fit_basis="")
    entry = ledger.build_entry(rec, batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert entry["gates"]["path"]["passed"] is False
    assert entry["gates"]["b2b_floor"] is True
    assert entry["scoring"]["bg_fit"]["score"] is None          # n/a legibility, not a low score
    types = {f["type"] for f in entry["flags"]}
    assert "b2b_floor" in types and "low_score_floor" not in types   # gate floor != low-score floor
    assert entry["recommended_action"] == "accept"              # clean gate-floor -> bulk-confirm


def test_floored_vs_low_vs_readfail_are_distinct():
    gate = ledger.build_entry(_rec(path_passed=False, gate_floored=True, floor_ok=False, model_priority="P3"),
                              batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    low = ledger.build_entry(_rec(background_fit=4, pmf=10, floor_ok=False, model_priority="P3"),
                             batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    readfail = ledger.build_entry(_rec(background_fit=None, pmf=10, floor_ok=False, model_priority="P3",
                                       background_fit_basis=""),
                                  batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert gate["gates"]["path"]["passed"] is False                          # gate floor
    assert low["gates"]["path"]["passed"] is True and low["scoring"]["floor_rule"]["passed"] is False  # low score
    assert "READ-FAILED" in readfail["scoring"]["floor_rule"]["reason"]      # bg read-failure, distinct label
    assert "READ-FAILED" not in low["scoring"]["floor_rule"]["reason"]


def test_tier_review_routes_to_review_override():
    rec = _rec(background_fit=7, pmf=6, strain=1, final_score=14, model_priority="P2", tier_review=True)
    entry = ledger.build_entry(rec, batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert entry["recommended_action"] == "review_override"
    assert "tier_review" in {f["type"] for f in entry["flags"]}


def test_growth_fence_emits_data_gap_and_reviews():
    rec = _rec(growth=4, growth_band="unknown", growth_basis="counts-scale",
               growth_note="unknown(covered-lives) [FENCED:counts-scale]", model_priority="P1", final_score=15)
    entry = ledger.build_entry(rec, batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert "data_gap" in {f["type"] for f in entry["flags"]}
    assert entry["recommended_action"] == "review_override"


def test_derived_final_priority_after_manual_override():
    entry = ledger.build_entry(_rec(model_priority="P3", floor_ok=False, background_fit=4),
                               batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    entry["decision"]["human_override"] = "P1"
    assert ledger.final_priority(entry) == "P1"
    assert ledger.final_priority_code(entry) == "P1"
    assert ledger.provenance(entry) == "human-overridden"


def test_b2b_background_fit_and_final_are_na_but_others_compute():
    # A B2B company (no consumer end-user): bg + FINAL are n/a by definition; ARR/Growth/Strain still compute.
    rec = _rec(company="medically home", business_model="B2B", funding_stage="series-c",
               background_fit=None, pmf=6, arr_level=7, growth=5, strain=1, final_score=13,
               path_passed=False, agency_passed=False, gate_floored=True, floor_ok=False, model_priority="P3")
    entry = ledger.build_entry(rec, batch_id=BATCH, date_scored=DATE, framework_version="v1.25")
    assert entry["scoring"]["bg_fit"]["score"] is None and "n/a" in entry["scoring"]["bg_fit"]["rationale"]
    assert entry["scoring"]["final_score"] is None
    assert entry["scoring"]["pmf"]["arr_level"]["score"] == 7 and entry["scoring"]["strain"]["score"] == 1
    flat = ledger.flatten_entry(entry)
    assert flat["Background Fit"] == "n/a (no consumer end-user)"
    assert flat["FINAL"] == "n/a"
    assert flat["ARR"] == 7 and flat["Growth"] == 5


def test_score_checkpoint_row_threads_bg_reasoning():
    import json
    fb = {"maturity_evidence": {"funding_rounds": [{"series_designation": "series-b", "type": "series-b",
                                                    "date": "2023-01", "is_priced_equity": True}], "ipo_event": {}},
          "commercial_evidence": {"revenue_or_arr": "$20M"}, "capability_evidence": {"a2_score": 60},
          "reset_evidence": {"reset_events": []}}
    row = {"company": "x", "fit_brief_json": json.dumps(fb),
           "operating_characteristics_finding": "daily", "commercial_scale_finding": "scaled", "outcomes_finding": "good"}
    rec = se.score_checkpoint_row(
        row, classifier_read={"who_uses": "consumer", "who_pays": "consumer", "who_uses_confidence": "high"},
        growth_read={"growth_band": "solid", "growth_basis": "revenue-rate", "growth_evidence": "+60% YoY"},
        background_fit=7, background_fit_basis="daily habit loop", data_feedback_loop="yes")
    assert rec["background_fit"] == 7
    assert rec["background_fit_basis"] == "daily habit loop"   # the live read's reasoning overrides stale fit_brief
    assert rec["data_feedback_loop"] == "yes"


def test_score_company_surfaces_rationale_passthrough():
    # B1: score_company now carries the per-component reasons/details the ledger renders.
    row = {"company": "x", "who_uses": "consumer", "who_pays": "consumer", "funding_stage": "series-b",
           "revenue_or_arr": "$20M ARR", "growth_band": "solid", "growth_basis": "revenue-rate",
           "growth_evidence": "+60% YoY", "background_fit_basis": "daily use", "data_feedback_loop": "yes",
           "operating_characteristics_finding": "scaling", "capability_a2_score": "60",
           "reset_events_json": "[]"}   # score_company requires a flattened row (reset column present)
    rec = se.score_company(row, background_fit=7)
    for key in ("path_passed", "agency_passed", "path_detail", "agency_detail", "strain_strength",
                "strain_rationale", "growth_band", "growth_note", "background_fit_basis",
                "data_feedback_loop", "reset_detail", "business_model_needs_review"):
        assert key in rec, f"missing passthrough key: {key}"
