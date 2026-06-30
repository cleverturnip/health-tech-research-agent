"""Commit 8 — deterministic tests for the end-to-end orchestrator (`score_company`) + the R1 re-validation
harness (`revalidate_r1`), the §B7 v1.20 STABILITY MACHINERY at roster scale.

`score_company` is exercised on synthetic rows (gates -> scores -> assemble). `revalidate_r1` is exercised
on SEEDED N-run rosters that encode the DOCUMENTED behaviors (a tier-mover, a human override, stable
companies, floored companies) — proving the harness logic GIVEN inputs. The real-data named distribution
(4/6/6/38 with season the mover, the six FINAL-14 stable) is the LIVE Colab 5x run, NOT proven here.
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
        "capability_a2_score": "60", "operating_characteristics": "",
        "background_fit": "7",
    }
    base.update(kw)
    return base


def test_score_company_b2c_floor_pass_runs_to_a_tier():
    out = se.score_company(_row())
    assert out["business_model"] == "B2C"
    assert out["funding_stage"] == "series-b"
    assert out["floor_ok"] is True
    assert out["layer"] == "stability"
    assert out["model_priority"] in se.PRIORITY_TIERS


def test_score_company_background_fit_argument_overrides_row():
    # the R1 harness passes a fresh bg_fit each run; the argument wins over the row column
    low = se.score_company(_row(background_fit="7"), background_fit=4)
    assert low["background_fit"] == 4
    assert low["floor_ok"] is False          # bg_fit=4 -> floor-FAIL
    assert low["model_priority"] == "P3"
    assert low["floor_reason"].startswith("floor-rule")


def test_score_company_b2b_floor_is_gate_floored():
    # a human-locked B2B floor company -> PATH Test A floor -> P3
    locked = next(iter(se.LOCKED_B2B_FLOOR))
    out = se.score_company(_row(company=locked, who_uses="professional"))
    assert out["business_model"] == "B2B"
    assert out["layer"] == "floor"
    assert out["model_priority"] == "P3"
    assert out["floor_reason"].startswith("PATH Test A")


def test_score_company_applies_human_locked_stage_override():
    # signos: persisted funding_stage may read series-c; the v1.14 override forces series-b
    out = se.score_company(_row(company="signos", funding_stage="series-c"))
    assert out["funding_stage"] == "series-b"


def test_score_company_function_override_is_terminal():
    # Function Health: floor-FAIL by rule (bg_fit=4) -> model P3, human override -> final P1
    out = se.score_company(_row(company="function health", background_fit="4"))
    assert out["model_priority"] == "P3"
    assert out["human_override"] == "P1"
    assert out["final_priority"] == "P1"
    assert out["layer"] == "override"


# ---------------------------------------------------------------------------
# revalidate_r1 — seeded N-run rosters
# ---------------------------------------------------------------------------

def _rosters_from_vectors(vectors, overrides, n):
    """Build N run-rosters from {company: [tier per run]} + {company: override}."""
    return [
        [{"company": co, "model_priority": tiers[i], "human_override": overrides.get(co)}
         for co, tiers in vectors.items()]
        for i in range(n)
    ]


def _synthetic_r1(n=5):
    """A synthetic 54-company R1 that hits 4/6/6/38: 4 stable P0; 4 stable P1; `season` the one mover
    (P2<->P1) -> P1 flagged; `function` override -> P1 (model vector P3); 6 stable P2 (the FINAL-14 stand-
    ins); 38 floored P3. NOT the real names/distribution — the harness logic, on documented behaviors."""
    vectors, overrides = {}, {}
    for i in range(4):
        vectors[f"p0_{i}"] = ["P0"] * n
    for i in range(4):
        vectors[f"p1_{i}"] = ["P1"] * n
    vectors["season"] = ["P2", "P1", "P2", "P2", "P1"][:n]          # the mover -> P1 flagged
    vectors["function"] = ["P3"] * n                                 # floor-FAIL model call...
    overrides["function"] = "P1"                                     # ...lifted by the override
    for i in range(6):
        vectors[f"p2_{i}"] = ["P2"] * n                              # the six FINAL-14 stand-ins (stable)
    for i in range(38):
        vectors[f"floored_{i}"] = ["P3"] * n
    return vectors, overrides


def test_revalidate_r1_clean_run_hits_target():
    vectors, overrides = _synthetic_r1()
    rep = se.revalidate_r1(_rosters_from_vectors(vectors, overrides, 5))
    assert rep["passed"] is True
    assert rep["tally"] == {"P0": 4, "P1": 6, "P2": 6, "P3": 38}
    assert rep["target"] == se.R1_TARGET
    # season is the one flagged straddler; the six P2 stand-ins are NOT flagged
    assert rep["tier_variance"] == ["season"]
    assert rep["resolved"]["season"] == {"final_priority": "P1", "tier_variance": True}
    assert rep["resolved"]["function"] == {"final_priority": "P1", "tier_variance": False}
    assert rep["resolved"]["p2_0"]["tier_variance"] is False


def test_revalidate_r1_surfaces_drift_does_not_force_target():
    # perturb one stable P2 into a mover -> it bumps to P1 -> tally P1=7 / P2=5: a FAILED R1, surfaced.
    vectors, overrides = _synthetic_r1()
    vectors["p2_0"] = ["P2", "P1", "P2", "P2", "P2"]    # now a mover
    rep = se.revalidate_r1(_rosters_from_vectors(vectors, overrides, 5))
    assert rep["passed"] is False
    assert rep["tally"]["P1"] == 7 and rep["tally"]["P2"] == 5
    assert rep["discrepancies"]["P1"] == {"target": 6, "actual": 7}
    assert rep["discrepancies"]["P2"] == {"target": 6, "actual": 5}
    assert "p2_0" in rep["tier_variance"]               # the drifting company is named, not hidden


def test_revalidate_r1_floor_wobbler_is_flagged_not_dropped():
    # a company floor-PASS in some runs, floor-FAIL (P3) in others -> unstable -> highest + flag
    vectors = {"wobbler": ["P2", "P3", "P2", "P2", "P3"]}
    rep = se.revalidate_r1(_rosters_from_vectors(vectors, {}, 5))
    assert rep["resolved"]["wobbler"] == {"final_priority": "P2", "tier_variance": True}
    assert rep["tier_variance"] == ["wobbler"]


def test_revalidate_r1_flags_company_missing_from_a_run():
    # 'ghost' appears in only 4 of 5 runs -> inconsistent (a run/data fault, not silently tallied clean)
    runs = _rosters_from_vectors({"a": ["P1"] * 5, "ghost": ["P1"] * 5}, {}, 5)
    runs[2] = [rec for rec in runs[2] if rec["company"] != "ghost"]
    rep = se.revalidate_r1(runs)
    assert rep["inconsistent_companies"] == ["ghost"]
    assert rep["passed"] is False


def test_revalidate_r1_requires_at_least_one_run():
    with pytest.raises(ValueError):
        se.revalidate_r1([])
