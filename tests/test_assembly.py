"""Commit 7 — deterministic tests for the §B7 FINAL ASSEMBLY (SOT v1.20).

FINAL = background_fit + pmf + strain; the FLOOR RULE (bg_fit > 4 AND pmf > 4) gates FIRST (floor-FAIL ->
P3 regardless of FINAL); thresholds P0 >=18 / P1 15-17 / P2 13-14 / P3 <13 apply ONLY to floor-PASS. Three
layers, each company handled by EXACTLY ONE: override (Rule 6, terminal) -> floor -> stability (the v1.20
N=5 run-to-run detector, tested here on SEEDED tier-vectors; the live 5x sampling is the Commit-8 R1 run).
Fully deterministic — no LLM.
"""

import pytest

from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# threshold_tier — exact boundaries (18/17/15/14/13/12)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("final_score, tier", [
    (30, "P0"), (18, "P0"),          # P0 >= 18
    (17, "P1"), (15, "P1"),          # P1 15-17
    (14, "P2"), (13, "P2"),          # P2 13-14
    (12, "P3"), (0, "P3"),           # P3 < 13
])
def test_threshold_tier_exact_boundaries(final_score, tier):
    assert se.threshold_tier(final_score) == tier


def test_threshold_tier_non_numeric_is_p3():
    # never a silent pass
    assert se.threshold_tier(None) == "P3"
    assert se.threshold_tier(True) == "P3"   # bool is not a real FINAL


# ---------------------------------------------------------------------------
# floor_rule_pass — strict > 4 on BOTH halves
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bg, pmf, ok", [
    (5, 5, True),
    (10, 5, True),
    (5, 4, False),     # pmf == 4 is NOT > 4
    (4, 5, False),     # bg == 4 is NOT > 4
    (4, 4, False),
    (None, 7, False),  # absent half -> FAIL
    (7, None, False),
])
def test_floor_rule_strict_gt4_both(bg, pmf, ok):
    assert se.floor_rule_pass(bg, pmf) is ok


# ---------------------------------------------------------------------------
# tier_stability — the v1.20 N=5 RUN-TO-RUN detector (seeded vectors)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("run_tiers, resolved, variance", [
    (["P2", "P2", "P2", "P2", "P2"], "P2", False),   # STABLE -> that tier, no flag
    (["P1", "P1", "P1", "P1", "P1"], "P1", False),
    (["P2", "P2", "P1", "P2", "P2"], "P1", True),    # one cross UP -> highest + flag
    (["P2", "P1", "P2", "P1", "P2"], "P1", True),    # season-like: tier MOVES -> P1 flagged
    (["P3", "P2", "P2", "P2", "P2"], "P2", True),    # one cross down-tier present -> highest = P2 + flag
    (["P1", "P0", "P1", "P1", "P1"], "P0", True),    # highest observed wins
])
def test_tier_stability_seeded_vectors(run_tiers, resolved, variance):
    assert se.tier_stability(run_tiers) == (resolved, variance)


def test_tier_stability_rejects_empty_and_malformed():
    # a malformed run tier must NEVER silently read as 'stable'
    with pytest.raises(ValueError):
        se.tier_stability([])
    with pytest.raises(ValueError):
        se.tier_stability(["P2", "P9", "P2"])


# ---------------------------------------------------------------------------
# canonical growth evidence wiring (§B6.1 v1.18)
# ---------------------------------------------------------------------------

def test_canonical_growth_evidence_uses_the_three_fields_not_commercial_scale():
    row = {
        "growth_signal": "ARR up sharply",
        "revenue_or_arr": "Latka: $8M (2024) -> $12.3M (2025)",
        "growth_finding": "derived ~53.7% YoY",
        "commercial_scale_finding": "WRONG FIELD — must not appear",
    }
    out = se.canonical_growth_evidence(row)
    assert "Latka" in out and "53.7" in out and "ARR up sharply" in out
    assert "WRONG FIELD" not in out


def test_canonical_growth_evidence_drops_empty_fields():
    assert se.canonical_growth_evidence({"revenue_or_arr": "$10M"}) == "$10M"
    assert se.canonical_growth_evidence({}) == ""


# ---------------------------------------------------------------------------
# build_floor_reason — review-grade detail per source (v1.15)
# ---------------------------------------------------------------------------

def test_floor_reason_pathA_human_locked_vs_classifier():
    # human-locked floor list (a member of LOCKED_B2B_FLOOR)
    locked = next(iter(se.LOCKED_B2B_FLOOR))
    r1 = se.build_floor_reason(locked, business_model="B2B", path_passed=False,
                               path_reason="Test A: B2B floor", agency_passed=True,
                               agency_reason="", floor_ok=False, background_fit=None, pmf=None)
    assert "human-locked floor list" in r1
    # a NON-listed B2B -> classifier read
    r2 = se.build_floor_reason("some startup", business_model="B2B", path_passed=False,
                               path_reason="Test A: B2B floor", agency_passed=True,
                               agency_reason="", floor_ok=False, background_fit=None, pmf=None)
    assert "classifier read who_uses=professional" in r2


def test_floor_reason_pathB_shows_what_was_looked_for():
    r = se.build_floor_reason("co", business_model="B2C", path_passed=False,
                              path_reason="Test B (B2C): DEAD — no revenue, user-scale, or growth signal",
                              agency_passed=True, agency_reason="", floor_ok=False,
                              background_fit=None, pmf=None)
    assert r.startswith("PATH Test B: engine-not-alive")
    assert "no revenue" in r


def test_floor_reason_agency_carries_stage_and_reset_detail():
    r = se.build_floor_reason("co", business_model="B2C", path_passed=True, path_reason="ok",
                              agency_passed=False, agency_reason="series-d-plus late-stage (no reset)",
                              floor_ok=True, background_fit=7, pmf=7,
                              reset_detail="reset events [CFO hire -> exec-add / unclear]; none fired")
    assert r.startswith("AGENCY-fail")
    assert "series-d-plus" in r and "none fired" in r


def test_floor_reason_floor_rule_names_the_failing_gradient():
    r = se.build_floor_reason("co", business_model="B2C", path_passed=True, path_reason="ok",
                              agency_passed=True, agency_reason="ok", floor_ok=False,
                              background_fit=4, pmf=7)
    assert r.startswith("floor-rule")
    assert "bg_fit=4" in r and "pmf=7" in r


def test_floor_reason_empty_for_passing_company():
    assert se.build_floor_reason("co", business_model="B2C", path_passed=True, path_reason="ok",
                                 agency_passed=True, agency_reason="ok", floor_ok=True,
                                 background_fit=7, pmf=7) == ""


# ---------------------------------------------------------------------------
# assemble_priority — the full floor -> override -> stability precedence
# ---------------------------------------------------------------------------

def _passing(**kw):
    """A floor-PASS, gates-pass company; override per-field."""
    base = dict(business_model="B2C", path_passed=True, path_reason="ok",
                agency_passed=True, agency_reason="ok", background_fit=7, pmf=7, strain=1)
    base.update(kw)
    return base


def test_assemble_floor_pass_single_run_uses_model_tier():
    # bg 7 + pmf 7 + strain 1 = 15 -> P1; floor-PASS; no override; no run_tiers -> model tier stands.
    out = se.assemble_priority("acme", **_passing())
    assert out["final_score"] == 15
    assert out["floor_ok"] is True
    assert out["layer"] == "stability"
    assert (out["model_priority"], out["final_priority"], out["tier_variance"]) == ("P1", "P1", False)


def test_assemble_floor_pass_with_run_tiers_runs_stability():
    # season-like floor-PASS straddler: tiers MOVE across runs -> highest + flag.
    out = se.assemble_priority("season", run_tiers=["P2", "P1", "P2", "P2", "P1"], **_passing())
    assert out["layer"] == "stability"
    assert out["model_priority"] == "P1"
    assert out["tier_variance"] is True


def test_assemble_floor_pass_stable_run_tiers_no_flag():
    # the FINAL-14 case: stable at P2 across all 5 runs -> P2, no flag.
    out = se.assemble_priority("foodsmart", run_tiers=["P2"] * 5,
                               **_passing(background_fit=7, pmf=6, strain=1))  # 14 -> P2
    assert out["model_priority"] == "P2"
    assert out["tier_variance"] is False


def test_assemble_floor_rule_fail_is_p3_with_reason():
    # gates pass but bg_fit=4 -> floor-FAIL -> P3 (Angle/Oula "P3-by-floor").
    out = se.assemble_priority("angle", **_passing(background_fit=4, pmf=7, strain=1))
    assert out["layer"] == "floor"
    assert out["model_priority"] == "P3" and out["final_priority"] == "P3"
    assert out["tier_variance"] is False
    assert out["floor_reason"].startswith("floor-rule")


def test_assemble_gate_floored_is_p3_with_path_reason():
    out = se.assemble_priority("medforce", business_model="B2B", path_passed=False,
                               path_reason="Test A: B2B floor", agency_passed=True, agency_reason="",
                               background_fit=None, pmf=None, strain=0)
    assert out["layer"] == "floor"
    assert out["model_priority"] == "P3"
    assert out["floor_reason"].startswith("PATH Test A")


def test_assemble_human_override_is_terminal_and_separate():
    # Function Health: floor-FAIL by rule (bg_fit=4) -> model_priority P3; human override -> final P1.
    out = se.assemble_priority("function health", **_passing(background_fit=4, pmf=4, strain=0))
    assert out["layer"] == "override"
    assert out["model_priority"] == "P3"          # the pure §B call is preserved (never collapsed)
    assert out["human_override"] == "P1"
    assert out["final_priority"] == "P1"          # override wins (Rule 6)
    assert out["tier_variance"] is False          # overridden -> NOT scored for stability / NOT flagged


def test_assemble_override_skips_stability_even_when_floor_pass():
    # a (hypothetical) floor-PASS company that is ALSO in the override map: stability is NOT run on it,
    # the override is terminal, no tier_variance flag.
    se.DOCUMENTED_PRIORITY_OVERRIDES["edge co"] = "P0"
    try:
        out = se.assemble_priority("edge co", run_tiers=["P2", "P1", "P2", "P1", "P2"], **_passing())
        assert out["layer"] == "override"
        assert out["final_priority"] == "P0"
        assert out["tier_variance"] is False
    finally:
        del se.DOCUMENTED_PRIORITY_OVERRIDES["edge co"]


def test_assemble_exactly_one_layer():
    # every routing returns exactly one of the three layer labels
    layers = {
        se.assemble_priority("acme", **_passing())["layer"],
        se.assemble_priority("angle", **_passing(background_fit=4))["layer"],
        se.assemble_priority("function health", **_passing(background_fit=4, pmf=4))["layer"],
    }
    assert layers == {"stability", "floor", "override"}
