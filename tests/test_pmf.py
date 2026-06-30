"""Commit 5a — deterministic tests for the §B6 PMF scoring (Scale A + Scale B + interp + assembly).

Built against SOT §B6 v1.8 (LOCKED scales + geometric interp, parity confirmed at plan D5) + the v1.12
ratified behaviors (single-absent-half neutral=4; unknown-stage -> series-b; cap@7 inert in the growth-
absent path). NO acceleration. Fully deterministic — the growth-RATE EXTRACTION (text -> structured read)
is the Commit-5b LLM step; this layer SCORES a structured read.
"""

import pytest

from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# SCALE A (ARR) — the SOT §B6 asserts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("revenue, stage, expected", [
    ("$24M ARR", "series-a", 7),
    ("$50M ARR", "series-a", 10),
    ("$4M ARR", "series-a", 1),
    ("$39.3M ARR (published point)", "series-a", 9),
])
def test_scale_a_arr_level_asserts(revenue, stage, expected):
    assert se.arr_level_score(revenue, stage) == expected


def test_arr_level_none_when_no_figure():
    assert se.arr_level_score("no revenue disclosed", "series-b") is None


def test_money_takes_the_max_and_handles_billions():
    assert se._money("est $500M in 2024 and $1B in 2025") == 1e9


# ---------------------------------------------------------------------------
# SCALE B (growth) — the SOT §B6 asserts (NO acceleration); growth read is structured
# ---------------------------------------------------------------------------

def _rate(pct):
    return {"kind": "rate", "rate_pct": pct}


@pytest.mark.parametrize("pct, stage, expected", [
    (450, "series-b", 10),     # Function +450%/SerB -> 10
    (200, "series-b", 10),     # Fay +200%/SerB -> 10
    (51, "public", 7),         # Hinge +51%/public -> 7
    (26, "series-d-plus", 4),  # Maven +26%/D+ -> 4 (series-d-plus reads the public row)
])
def test_scale_b_growth_rate_asserts(pct, stage, expected):
    score, _note = se.score_growth(_rate(pct), stage)
    assert score == expected


def test_growth_stage_maps_d_plus_to_public_row():
    assert se._growth_stage("series-d-plus") == "public"
    assert se._growth_stage("public") == "public"
    assert se._growth_stage("series-b") == "series-b"


def test_no_acceleration_growth_is_base_scale_b_only():
    # +51% at public is base 7 — never inflated to 8 (acceleration removed/parked v1.8).
    score, _ = se.score_growth(_rate(51), "public")
    assert score == 7


# ---------------------------------------------------------------------------
# zero-baseline (arr=growth collapse) + qualitative fallbacks + absent
# ---------------------------------------------------------------------------

def test_zero_baseline_scores_magnitude_via_scale_a():
    # a $0 -> $112M launch at Series-C scores the magnitude on Scale A (the arr=growth collapse).
    score, _ = se.score_growth({"kind": "zero_baseline", "magnitude_usd_m": 112}, "series-c")
    assert score == se.arr_level_score("$112M", "series-c")   # same Scale-A value
    assert score is not None


@pytest.mark.parametrize("q, expected", [("declining", 1), ("flat", 3), ("growing", 5)])
def test_qualitative_no_rate_fallbacks(q, expected):
    score, _ = se.score_growth({"kind": "qualitative", "qualitative": q}, "series-b")
    assert score == expected


def test_absent_growth_is_none():
    score, _ = se.score_growth({"kind": "absent"}, "series-b")
    assert score is None


# ---------------------------------------------------------------------------
# §B6.1 fence — revenue/$ growth only; counts are SCALE (the extractor's guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, fenced", [
    ("covered lives grew 50%", True),         # pomelo case (covered-lives)
    ("485% patient growth", True),            # outcomes4me case (patients)
    ("headcount 100 -> 500", True),
    ("50% member reach growth", True),        # "member reach" is in the fence
    ("revenue grew ~53.7% YoY", False),       # season case (a real revenue rate)
    ("$235M -> $471M ARR", False),
    # NOTE: bare "250,000 members" is NOT caught by the deterministic fence (spike parity — the spike
    # _FENCE has "member reach", not bare "members"); the Commit-5b LLM extractor handles that general case.
    ("250,000 members", False),
])
def test_b6_1_fence(text, fenced):
    assert se.is_fenced_count_context(text) is fenced


# ---------------------------------------------------------------------------
# PMF assembly — 40/60, round-even, single-absent-half=4, cap@7 (inert in growth-absent path)
# ---------------------------------------------------------------------------

def test_pmf_blend_both_present():
    assert se.pmf_score(10, 10) == (10, False)
    assert se.pmf_score(7, 6) == (6, False)     # round(0.4*7 + 0.6*6) = round(6.4) = 6


def test_pmf_single_absent_half_neutral_4():
    # arr absent -> al=4; growth present
    assert se.pmf_score(None, 8) == (6, False)  # round(0.4*4 + 0.6*8) = round(6.4) = 6; no cap (growth present)
    # growth absent -> g=4 AND cap fires (but inert)
    val, capped = se.pmf_score(10, None)
    assert capped is True
    assert val == 6                             # round(0.4*10 + 0.6*4) = round(6.4) = 6 -> min(6,7) no-op


def test_pmf_both_absent_is_4():
    assert se.pmf_score(None, None) == (4, True)  # round(0.4*4 + 0.6*4) = 4


def test_cap7_never_binds_in_growth_absent_path():
    # with growth absent, the 60%-weight half is held at 4 -> raw <= 6.4 -> val <= 6 < 7, for any arr.
    for al in range(1, 11):
        val, capped = se.pmf_score(al, None)
        assert capped is True
        assert val <= 6     # the cap@7 is redundant-but-harmless (v1.12 note)
