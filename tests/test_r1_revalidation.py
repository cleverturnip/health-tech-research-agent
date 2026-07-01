"""Commit 8 (v1.22) — deterministic tests for the end-to-end orchestrator (`score_company`) + the R1 tally
(`tally_r1`, single-roster, reproducible-by-caching; the retired N=5 `revalidate_r1` is gone).

`score_company` is exercised on synthetic rows (gates -> scores -> assemble). `tally_r1` is exercised on a
SEEDED single roster (already-scored records) — it counts the finals, checks the tally vs a target (an
OUTPUT check, never forced), and surfaces the BOUNDED-REVIEW set (tier_review / override / floor_reason).
Fully deterministic — no LLM.
"""

import pytest

from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# score_company — end-to-end on synthetic rows
# ---------------------------------------------------------------------------

def _row(**kw):
    base = {
        "company": "acme",
        "who_uses": "consumer", "who_pays": "consumer", "who_uses_confidence": "high",
        "funding_stage": "series-b", "ipo_status": "private",
        "reset_events_json": "[]", "reset_event_types": "",
        "revenue_or_arr": "$60M ARR", "sponsored_user_scale": "", "paying_customer_count": "",
        "growth_signal": "growing", "payer_institutional_finding": "", "business_model_type": "",
        "growth_kind": "rate", "growth_rate_pct": "100", "growth_magnitude_usd_m": "",
        "growth_qualitative": "", "growth_source": "company",
        "capability_a2_score": "60", "operating_characteristics_finding": "",
        "background_fit": "7",
    }
    base.update(kw)
    return base


def test_score_company_b2c_floor_pass_runs_to_a_tier():
    out = se.score_company(_row())
    assert out["business_model"] == "B2C"
    assert out["funding_stage"] == "series-b"
    assert out["floor_ok"] is True
    assert out["layer"] == "threshold"
    assert out["model_priority"] in se.PRIORITY_TIERS


def test_score_company_background_fit_argument_overrides_row():
    # the reads are injected; the argument wins over the row column
    low = se.score_company(_row(background_fit="7"), background_fit=4)
    assert low["background_fit"] == 4
    assert low["floor_ok"] is False          # bg_fit=4 -> floor-FAIL
    assert low["model_priority"] == "P3"
    assert low["floor_reason"].startswith("floor-rule")


def test_score_company_b2b_floor_is_gate_floored():
    locked = next(iter(se.LOCKED_B2B_FLOOR))
    out = se.score_company(_row(company=locked, who_uses="professional"))
    assert out["business_model"] == "B2B"
    assert out["layer"] == "floor"
    assert out["model_priority"] == "P3"
    assert out["floor_reason"].startswith("PATH Test A")


def test_score_company_applies_human_locked_stage_override():
    out = se.score_company(_row(company="signos", funding_stage="series-c"))
    assert out["funding_stage"] == "series-b"


def test_score_company_function_override_is_terminal():
    out = se.score_company(_row(company="function health", background_fit="4"))
    assert out["model_priority"] == "P3"
    assert out["human_override"] == "P1"
    assert out["final_priority"] == "P1"
    assert out["layer"] == "override"


# ---------------------------------------------------------------------------
# tally_r1 — single roster of already-scored records
# ---------------------------------------------------------------------------

def _rec(company, final_priority, *, tier_review=False, human_override=None, floor_reason="",
         layer="threshold", final_score=15):
    return {"company": company, "final_priority": final_priority, "tier_review": tier_review,
            "human_override": human_override, "floor_reason": floor_reason, "layer": layer,
            "final_score": final_score, "background_fit": 7, "pmf": 7, "strain": 1,
            "funding_stage": "series-b", "arr_level": 5}


def test_tally_r1_counts_and_hits_target():
    roster = [_rec("a", "P0"), _rec("b", "P1"), _rec("c", "P2"), _rec("d", "P3", layer="floor",
                                                                        floor_reason="floor-rule ...")]
    rep = se.tally_r1(roster, target={"P0": 1, "P1": 1, "P2": 1, "P3": 1})
    assert rep["passed"] is True
    assert rep["tally"] == {"P0": 1, "P1": 1, "P2": 1, "P3": 1}
    assert rep["discrepancies"] == {}


def test_tally_r1_surfaces_drift_not_forced():
    # two P1, zero P2 vs a target of one each -> surfaced, passed False (never forced to the target)
    roster = [_rec("a", "P0"), _rec("b", "P1"), _rec("c", "P1"), _rec("d", "P3", layer="floor")]
    rep = se.tally_r1(roster, target={"P0": 1, "P1": 1, "P2": 1, "P3": 1})
    assert rep["passed"] is False
    assert rep["discrepancies"]["P1"] == {"target": 1, "actual": 2}
    assert rep["discrepancies"]["P2"] == {"target": 1, "actual": 0}


def test_tally_r1_review_set_bounded_and_floor_audit_split():
    roster = [
        _rec("clean", "P0", final_score=20),                                  # interior, no flag
        _rec("borderline", "P1", tier_review=True, final_score=15),           # proximity-flagged
        _rec("override", "P1", human_override="P1", layer="override"),        # human override
        _rec("floored", "P3", layer="floor", floor_reason="floor-rule bg_fit=4 / pmf=3"),
        _rec("readfail", "P3", layer="floor", floor_reason="floor-rule bg_fit=READ-FAILED (None — re-take)"),
    ]
    rep = se.tally_r1(roster, target={"P0": 1, "P1": 2, "P3": 2})
    # BOUNDED review_set = proximity + override ONLY (the autonomy metric); floored -> floor_audit
    assert set(rep["review_set"]) == {"borderline", "override"}
    assert rep["review_set_size"] == 2
    assert "tier_review(proximity)" in rep["review_set"]["borderline"]
    assert "override(P1)" in rep["review_set"]["override"]
    # floored rejects are on-demand audit, NOT in the must-look set
    assert set(rep["floor_audit"]) == {"floored", "readfail"}
    assert "floored" not in rep["review_set"] and "clean" not in rep["review_set"]
    # a bg READ FAILURE is surfaced as a bug (never a silent legit floor)
    assert rep["read_failures"] == ["readfail"]


def test_tally_r1_detail_and_resolved_present():
    rep = se.tally_r1([_rec("a", "P1", tier_review=True)], target={"P1": 1})
    assert rep["resolved"]["a"] == {"final_priority": "P1", "tier_review": True,
                                    "layer": "threshold", "floor_reason": ""}
    assert rep["detail"]["a"]["final"] == 15 and rep["detail"]["a"]["bg_fit"] == 7
