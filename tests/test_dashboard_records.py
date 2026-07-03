"""Phase 2 — the dashboard read engine: per-company records + grid projections + §1a enforcement."""

import json
from pathlib import Path

import pytest

from health_tech_research_agent import dashboard, ledger

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


def _reviewed_entries():
    """The sample ledger, finalized (stamped reviewed) — the state the dashboard runs against."""
    entries = ledger.read_ledger(FIXTURE)
    return ledger.finalize_gate2_review(entries, reviewed_date="2026-07-03", reviewed_at_gate="gate2_sample")


# --- §1a gate invariant -----------------------------------------------------

def test_unreviewed_entries_are_refused():
    raw = ledger.read_ledger(FIXTURE)  # not finalized -> not reviewed
    with pytest.raises(dashboard.DashboardError) as exc:
        dashboard.build_company_records(raw)
    assert "GATE-2 invariant" in str(exc.value)


def test_reviewed_entries_build():
    records = dashboard.build_company_records(_reviewed_entries())
    assert len(records) == 5
    assert all(r["reviewed"] for r in records)


def test_require_reviewed_can_be_relaxed_for_testing():
    raw = ledger.read_ledger(FIXTURE)
    records = dashboard.build_company_records(raw, require_reviewed=False)
    assert len(records) == 5


# --- record content ---------------------------------------------------------

def test_records_carry_priority_provenance_and_override():
    records = {r["company"]: r for r in dashboard.build_company_records(_reviewed_entries())}
    beta = records["beta health"]
    assert beta["final_priority"] == "P1"        # human override wins
    assert beta["model_priority"] == "P3"
    assert beta["provenance"] == "human-overridden"
    assert beta["is_overridden"] is True
    assert beta["override"] == {"from": "P3", "to": "P1",
                                "reason": "strong revenue + growth; the low bg is the correct 2x/yr cadence"}

    alpha = records["alpha health"]
    assert alpha["final_priority"] == "P0"
    assert alpha["provenance"] == "model-accepted"
    assert alpha["override"] is None


def test_segment_label_join_and_tags():
    records = {r["company"]: r for r in dashboard.build_company_records(_reviewed_entries())}
    assert records["alpha health"]["segment_code"] == "METABOLIC_NUTRITION_HEALTH"
    assert records["alpha health"]["segment_label"] == "Metabolic, nutrition & weight health"
    assert records["gamma health"]["segment_label"] == "Specialty condition care"
    assert records["alpha health"]["tags"]["subsegment"] == ["diabetes"]
    assert records["alpha health"]["tags"]["data_input"] == ["labs"]


def test_b2b_gets_na_display_legibility():
    records = {r["company"]: r for r in dashboard.build_company_records(_reviewed_entries())}
    gamma = records["gamma health"]                     # B2B, gate-floored
    assert gamma["model"] == "B2B"
    assert gamma["bg_display"] == "n/a (no consumer end-user)"
    assert gamma["final_display"] == "n/a"
    assert gamma["scores"]["bg"] is None


def test_records_sorted_priority_then_final():
    order = [r["company"] for r in dashboard.build_company_records(_reviewed_entries())]
    # P0 alpha, P1 beta, then the P3s by FINAL desc: delta(18) > epsilon(7) > gamma(n/a)
    assert order == ["alpha health", "beta health", "delta health", "epsilon health", "gamma health"]


# --- all-companies view -----------------------------------------------------

def test_all_companies_view_columns_and_values():
    records = dashboard.build_company_records(_reviewed_entries())
    df = dashboard.all_companies_view(records)
    assert list(df.columns) == dashboard.ALL_COMPANIES_COLUMNS
    beta = df[df["company"] == "beta health"].iloc[0]
    assert beta["final_priority"] == "P1"
    assert beta["segment"] == "Metabolic, nutrition & weight health"
    assert beta["key_flag"] == "low_score_floor"      # warn beats the info override_candidate flag
    assert bool(beta["pursue"]) is False


# --- segment radar ----------------------------------------------------------

def test_segment_radar_counts_and_coverage():
    records = dashboard.build_company_records(_reviewed_entries())
    radar = {row["segment"]: row for _, row in dashboard.segment_radar_view(records).iterrows()}

    metabolic = radar["Metabolic, nutrition & weight health"]
    assert metabolic["companies"] == 2 and metabolic["P0"] == 1 and metabolic["P1"] == 1
    assert metabolic["desirable"] == 2
    assert metabolic["coverage"] == "Directional"     # 2 companies (<3) but ≥1 desirable

    mental = radar["Mental & behavioral health"]
    assert mental["companies"] == 1 and mental["desirable"] == 0
    assert mental["coverage"] == "Sparse"


def test_coverage_read_thresholds():
    assert dashboard.coverage_read(3, 2) == "Strong"
    assert dashboard.coverage_read(5, 1) == "Directional"   # ≥2 companies, ≥1 desirable
    assert dashboard.coverage_read(2, 1) == "Directional"
    assert dashboard.coverage_read(2, 0) == "Sparse"
    assert dashboard.coverage_read(1, 1) == "Sparse"


# --- research join ----------------------------------------------------------

def test_research_payload_extracts_evidence_not_retired_scores():
    fit_brief = {
        "verified_facts_with_sources": ["Series B $298M (2025-11). (prnewswire)"],
        "inferences": ["Scale is primarily D2C."],
        "unverified_or_weak_claims": ["No payer contracts found."],
        "commercial_evidence": {"revenue_or_arr": "~$100M run-rate (Sacra)", "growth_signal": "~450% YoY",
                                "q4_evidence_quality": "credible-estimate"},
        "maturity_evidence": {"funding_rounds": [{"type": "series-b", "amount": "$298M"}],
                              "total_funding": "$351M"},
        "capability_evidence": {"a2_score": 72, "a2_basis": "scaling complexity"},
        "taxonomy_classification": {"classification_rationale": "diagnostic lab testing"},
        # retired / non-input fields that must NOT surface as scores:
        "priority_gate_preliminary_result": "qualifies_for_p0",
        "scores": {"thesis_fit_score": {"score": 9}},
        "role_timing_assessment": {"why_now_or_why_not": "well funded"},
    }
    row = {"company": "function health", "fit_brief_json": json.dumps(fit_brief),
           "growth_finding": "long growth text ...", "outcomes_finding": ""}
    payload = dashboard.research_payload(row)

    assert payload["commercial"]["revenue_or_arr"] == "~$100M run-rate (Sacra)"
    assert payload["commercial"]["evidence_quality"] == "credible-estimate"
    assert payload["capability"]["a2_score"] == 72
    assert payload["classification_rationale"] == "diagnostic lab testing"
    assert payload["findings"] == {"growth_finding": "long growth text ..."}   # empty outcomes dropped
    # the retired / parallel fields are absent from the payload
    blob = json.dumps(payload)
    assert "thesis_fit_score" not in blob
    assert "priority_gate_preliminary_result" not in blob
    assert "why_now_or_why_not" not in blob


def test_records_join_research_when_provided():
    entries = _reviewed_entries()
    research = [{"company": "alpha health", "fit_brief_json": json.dumps(
        {"commercial_evidence": {"revenue_or_arr": "$80M ARR"}}), "funding_finding": "raised $50M"}]
    records = {r["company"]: r for r in dashboard.build_company_records(entries, research=research)}
    assert records["alpha health"]["research"]["commercial"]["revenue_or_arr"] == "$80M ARR"
    assert records["beta health"]["research"] is None    # no research row -> None
