"""§B6 PMF scoring tests — Scale A (ARR) + the v1.24 BAND growth read + PMF assembly.

Scale A (ARR-by-stage) + the geometric interp are LOCKED (SOT §B6 v1.8). The growth half is now a BAND
classification (§B6 v1.24 — HIGH=9/SOLID=6/SLOW=3/UNKNOWN=4; the figures/derive/rate schema + the growth-
absence cap are RETIRED). PMF = round(0.4*arr + 0.6*growth); the ARR half may be absent (-> neutral 4),
growth is ALWAYS a band value.
"""

import pytest

from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# SCALE A (ARR) — the SOT §B6 asserts (unchanged v1.24)
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
# GROWTH BAND (§B6 v1.24) — band -> score; growth is never None
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("band, expected", [("high", 9), ("solid", 6), ("slow", 3), ("unknown", 4)])
def test_growth_band_scores(band, expected):
    score, _ = se.score_growth({"growth_band": band}, "series-b")
    assert score == expected


def test_growth_stage_maps_d_plus_to_public_row():
    # (band cutoffs anchor to Scale B via _growth_stage; the map is unchanged v1.24)
    assert se._growth_stage("series-d-plus") == "public"
    assert se._growth_stage("public") == "public"
    assert se._growth_stage("series-b") == "series-b"


# ---------------------------------------------------------------------------
# §B6.1 fence — revenue/$ growth only; counts are SCALE (the extractor's guard, KEPT v1.24)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, fenced", [
    ("covered lives grew 50%", True),         # pomelo case (covered-lives)
    ("485% patient growth", True),            # outcomes4me case (patients)
    ("headcount 100 -> 500", True),
    ("50% member reach growth", True),        # "member reach" is in the fence
    ("revenue grew ~53.7% YoY", False),       # season case (a real revenue rate)
    ("$235M -> $471M ARR", False),
    ("250,000 members", False),
])
def test_b6_1_fence(text, fenced):
    assert se.is_fenced_count_context(text) is fenced


# ---------------------------------------------------------------------------
# PMF assembly — 40/60 blend, round, single-absent-ARR-half = neutral 4, NO growth-absence cap (v1.24)
# ---------------------------------------------------------------------------

def test_pmf_blend_both_present():
    assert se.pmf_score(10, 10) == 10
    assert se.pmf_score(7, 6) == 6              # round(0.4*7 + 0.6*6) = round(6.4) = 6


def test_pmf_absent_arr_half_neutral_4():
    # arr absent -> al=4; growth present (a band value)
    assert se.pmf_score(None, 8) == 6           # round(0.4*4 + 0.6*8) = round(6.4) = 6


def test_pmf_returns_a_bare_int_no_cap_tuple():
    # v1.24: the growth-absence cap is retired -> pmf_score returns a single int, not (val, capped).
    val = se.pmf_score(9, 9)
    assert isinstance(val, int) and val == 9


def test_pmf_growth_band_drives_the_blend():
    # a HIGH growth band (9) with a mid ARR (5) -> round(0.4*5 + 0.6*9) = round(7.4) = 7
    assert se.pmf_score(5, se.GROWTH_BAND_SCORE["high"]) == 7
    # an UNKNOWN band (4) with the same ARR -> round(0.4*5 + 0.6*4) = round(4.4) = 4
    assert se.pmf_score(5, se.GROWTH_BAND_SCORE["unknown"]) == 4
