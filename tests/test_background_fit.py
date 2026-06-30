"""Commit 4 — deterministic tests for the §B5 background-fit gradient (SOT §B5 v1.7, LOCKED prompt).

The prompt is LOCKED + validated (no co-draft); its LIVE re-run over the gate-passed companies is the
Colab validation (it should reproduce the frozen BG_FIT scores within tolerance). Offline here:
  1. PROMPT FIDELITY — the locked §B5 v1.7 wording is byte-faithful in the production prompt.
  2. PARSE / PRECONDITION — the who_uses==consumer guard + the flatten (clamp 1-10, normalize loop).
  3. FROZEN-REFERENCE TARGET — the frozen §B5 v1.7 scores (spike bg_fit_scores.py) are the validation
     reference: Nourish "periodic" regression = 8 (>=6, not floored); data_feedback_loop fires ONLY on
     the metabolic/tracking loops; Function low-frequency = 4 (correct + intended). These document what
     the live re-run must reproduce — they are NOT wired in as the scorer's output.
"""

import pytest

from health_tech_research_agent import research_runner as rr
from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# 1. Prompt fidelity — the locked §B5 v1.7 wording is in the production prompt.
# ---------------------------------------------------------------------------

def test_prompt_builds_and_substitutes():
    p = rr.build_background_fit_prompt("ACME Health", "EVIDENCE BLOB")
    assert "Company: ACME Health" in p
    assert "EVIDENCE BLOB" in p
    assert '{"background_fit"' in p          # JSON example single-braced after .format
    assert "{{" not in p and "}}" not in p


def test_prompt_carries_the_locked_scale_and_guards():
    p = rr.build_background_fit_prompt("X", "Y")
    assert 'mobile-games loop' in p
    assert "GRADIENT (1-10), not a pass/fail" in p
    assert "tight DATA-FEEDBACK LOOP" in p                      # 9-10 amplifier
    assert 'set data_feedback_loop = "yes"' in p
    assert "STILL SCORES SOLIDLY HERE" in p                     # 6-8 floor-protection band
    assert 'DO NOT under-score (the "periodic" trap)' in p       # the Nourish guard
    assert "Score 3-5 ONLY when the engagement is genuinely one-off / intermittent" in p


# ---------------------------------------------------------------------------
# 2. Precondition + flatten (deterministic)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("who_uses, applies", [
    ("consumer", True), ("Consumer", True), ("professional", False), ("", False),
])
def test_background_fit_precondition(who_uses, applies):
    assert se.background_fit_applies(who_uses) is applies


def test_flatten_parses_and_clamps():
    parsed = {"background_fit": {"background_fit": "8", "data_feedback_loop": "No",
                                 "basis": "recurring telehealth dietitian over months"}}
    cols = se.flatten_background_fit_fields(parsed)
    assert cols == {"background_fit": 8, "data_feedback_loop": "no",
                    "background_fit_basis": "recurring telehealth dietitian over months"}


def test_flatten_clamps_out_of_range_and_tolerates_missing():
    assert se.flatten_background_fit_fields({"background_fit": {"background_fit": 99}})["background_fit"] == 10
    assert se.flatten_background_fit_fields({"background_fit": {"background_fit": 0}})["background_fit"] == 1
    miss = se.flatten_background_fit_fields({"company": "x"})
    assert miss["background_fit"] is None
    assert miss["data_feedback_loop"] == ""


def test_flatten_normalizes_unrecognized_loop_to_blank():
    cols = se.flatten_background_fit_fields({"background_fit": {"background_fit": 5, "data_feedback_loop": "maybe"}})
    assert cols["data_feedback_loop"] == ""   # only yes/no kept


# ---------------------------------------------------------------------------
# 3. FROZEN §B5 v1.7 validation reference (spike bg_fit_scores.py) — the target the live run reproduces.
# ---------------------------------------------------------------------------

FROZEN_BG_FIT = {  # {company: (background_fit, data_feedback_loop)}
    "9amhealth": (8, "yes"), "affect therapeutics": (8, "no"), "allara health": (7, "no"),
    "angle health": (4, "no"), "berry street": (5, "no"), "bicycle health": (8, "no"),
    "counsel health": (4, "no"), "culina health": (6, "no"), "cylinder health": (4, "no"),
    "diana health": (4, "no"), "equip health": (7, "no"), "familywell health": (7, "no"),
    "fay": (7, "no"), "foodsmart": (7, "no"), "function health": (4, "no"), "grow therapy": (7, "no"),
    "insidetracker": (4, "no"), "jasper health": (7, "no"), "levels health": (9, "yes"),
    "nourish": (8, "no"), "oova": (7, "yes"), "oshi health": (5, "no"), "oula": (4, "no"),
    "outcomes4me": (5, "no"), "pelago": (8, "no"), "pomelo care": (7, "no"), "rula health": (7, "no"),
    "season health": (7, "no"), "signos": (9, "yes"), "solace health": (4, "no"),
    "summer health": (7, "no"), "tia": (4, "no"), "visana health": (5, "no"), "vivante health": (4, "no"),
    "waymark": (4, "no"), "wellist": (4, "no"), "zoe": (8, "no"),
}


def test_nourish_periodic_regression_reference_is_not_floored():
    # the Nourish "periodic" mislabel regression: a strong consumer habit -> 8, NOT floored as periodic.
    score, loop = FROZEN_BG_FIT["nourish"]
    assert score >= 6 and score == 8
    assert loop == "no"


def test_data_feedback_loop_fires_only_on_the_metabolic_tracking_loops():
    loop_yes = {co for co, (_s, lp) in FROZEN_BG_FIT.items() if lp == "yes"}
    assert loop_yes == {"levels health", "signos", "oova", "9amhealth"}


def test_function_low_frequency_reference_is_low_and_intended():
    # Function Health (2x/yr lab cadence) scores ~4 — correct + intended (the documented override candidate).
    assert FROZEN_BG_FIT["function health"] == (4, "no")


def test_all_frozen_scores_are_valid_gradient_values():
    for co, (score, loop) in FROZEN_BG_FIT.items():
        assert 1 <= score <= 10, co
        assert loop in ("yes", "no"), co
