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
# tier_review — the v1.22 PROXIMITY flag (single stable score within ±1 of a boundary)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("final, flagged", [
    (18, True),    # P0 edge (18-1=17 -> P1)
    (17, True),    # P1 edge up (17+1=18 -> P0)
    (16, False),   # P1 interior (15,17 both P1)
    (15, True),    # P1 edge down (15-1=14 -> P2)
    (14, True),    # P2 edge up (14+1=15 -> P1)
    (13, True),    # P2 edge down (13-1=12 -> P3)
    (12, True),    # near the 13 line (12+1=13 -> P2)
    (11, False),   # P3 interior
    (20, False),   # P0 interior
])
def test_tier_review_proximity(final, flagged):
    assert se.tier_review(final) is flagged


def test_tier_review_non_numeric_is_false():
    # a floored / absent score is not proximity-flagged (its review path is floor_reason)
    assert se.tier_review(None) is False
    assert se.tier_review(True) is False


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


def test_floor_reason_absent_bg_is_labeled_read_failed_not_a_silent_floor():
    # a gate-passed consumer reaching floor-rule with bg_fit=None is a READ FAILURE, not a legit low floor —
    # labeled LOUD so it can never hide as a clean floor (Fix 4 / wrong-and-silent guard at the floor level).
    r = se.build_floor_reason("co", business_model="B2C", path_passed=True, path_reason="ok",
                              agency_passed=True, agency_reason="ok", floor_ok=False,
                              background_fit=None, pmf=7)
    assert "READ-FAILED" in r
    # a real low score is NOT labeled a read failure
    r2 = se.build_floor_reason("co", business_model="B2C", path_passed=True, path_reason="ok",
                               agency_passed=True, agency_reason="ok", floor_ok=False,
                               background_fit=3, pmf=7)
    assert "READ-FAILED" not in r2 and "bg_fit=3" in r2


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


def test_assemble_floor_pass_uses_threshold_tier():
    # bg 7 + pmf 7 + strain 1 = 15 -> P1; floor-PASS; no override -> threshold tier stands. FINAL=15 is on
    # the P1/P2 boundary -> tier_review flagged.
    out = se.assemble_priority("acme", **_passing())
    assert out["final_score"] == 15
    assert out["floor_ok"] is True
    assert out["layer"] == "threshold"
    assert (out["model_priority"], out["final_priority"], out["tier_review"]) == ("P1", "P1", True)


def test_assemble_floor_pass_interior_score_not_flagged():
    # a floor-PASS company with FINAL well inside a tier band -> NOT proximity-flagged.
    out = se.assemble_priority("acme", **_passing(background_fit=9, pmf=9, strain=2))  # 20 -> P0 interior
    assert out["model_priority"] == "P0"
    assert out["tier_review"] is False


def test_assemble_floor_pass_boundary_score_is_flagged():
    # FINAL=14 (P2, one off the 15 line) -> tier_review flagged, tier stands P2 (NOT bumped).
    out = se.assemble_priority("foodsmart", **_passing(background_fit=7, pmf=6, strain=1))  # 14 -> P2
    assert out["model_priority"] == "P2"
    assert out["tier_review"] is True


def test_assemble_floor_rule_fail_is_p3_with_reason():
    # gates pass but bg_fit=4 -> floor-FAIL -> P3 (Angle/Oula "P3-by-floor"). Floored -> not proximity-flagged.
    out = se.assemble_priority("angle", **_passing(background_fit=4, pmf=7, strain=1))
    assert out["layer"] == "floor"
    assert out["model_priority"] == "P3" and out["final_priority"] == "P3"
    assert out["tier_review"] is False
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
    assert out["tier_review"] is False            # overridden -> NOT proximity-flagged


def test_assemble_override_is_terminal_not_proximity_flagged():
    # a (hypothetical) floor-PASS company that is ALSO in the override map: override is terminal, no
    # tier_review flag even if its FINAL sits on a boundary.
    se.DOCUMENTED_PRIORITY_OVERRIDES["edge co"] = "P0"
    try:
        out = se.assemble_priority("edge co", **_passing())  # FINAL 15 (boundary) but overridden
        assert out["layer"] == "override"
        assert out["final_priority"] == "P0"
        assert out["tier_review"] is False
    finally:
        del se.DOCUMENTED_PRIORITY_OVERRIDES["edge co"]


@pytest.mark.parametrize("gate_floored, bg, pmf, expect", [
    (False, 4, 7, True),    # floored on bg=4, pmf clears -> possible frozen-low -> flag
    (False, 3, 7, True),    # bg=3 within the ±2 band
    (False, 8, 7, False),   # bg=8 could not have wobbled below 5 -> not near
    (False, 2, 7, False),   # bg=2 too far below the line
    (False, 4, 4, False),   # pmf also fails -> bg is NOT the one thing holding it down
    (True, 4, 7, False),    # gate-floored (maturity / B2B) is deterministic -> bg wouldn't change it
    (False, None, 7, False),  # absent bg -> READ FAILURE flag, not this
])
def test_floored_bg_near_threshold(gate_floored, bg, pmf, expect):
    assert se.floored_bg_near_threshold(gate_floored=gate_floored, background_fit=bg, pmf=pmf) is expect


def test_assemble_surfaces_floored_bg_near_threshold():
    # grow-like: gates pass, pmf strong, but bg froze at 4 -> floored P3 AND flagged floored-but-close.
    out = se.assemble_priority("growco", **_passing(background_fit=4, pmf=8, strain=2))
    assert out["layer"] == "floor" and out["model_priority"] == "P3"
    assert out["floored_bg_near_threshold"] is True
    # a clean floor-PASS company is not flagged
    assert se.assemble_priority("acme", **_passing())["floored_bg_near_threshold"] is False


def test_assemble_exactly_one_layer():
    # every routing returns exactly one of the three layer labels
    layers = {
        se.assemble_priority("acme", **_passing())["layer"],
        se.assemble_priority("angle", **_passing(background_fit=4))["layer"],
        se.assemble_priority("function health", **_passing(background_fit=4, pmf=4))["layer"],
    }
    assert layers == {"threshold", "floor", "override"}
