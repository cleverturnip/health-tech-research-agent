"""§B6 v1.24 — deterministic tests for the BAND-CLASSIFICATION growth extractor (signed-off wording).

The extractor is LLM-facing; its LIVE validation is the Colab R1 run. Offline here:
  1. PROMPT FIDELITY — the band schema, the STAGE-AWARE Scale-B cutpoints, and the §B6.1 fence are
     byte-faithful in the production prompt.
  2. PARSE — normalize_growth_read / flatten_growth_read (band normalization; malformed -> unknown).
  3. SCORE INTEGRATION — score_growth maps band -> score (HIGH=9 / SOLID=6 / SLOW=3 / UNKNOWN=4).
  4. BAND-vs-SCALE-B ±2 VALIDATION — band_for_rate agrees with the retired Scale-B interpolation within ±2
     on the named clean-rate anchors (the bands preserve the phase-relative intent).
"""

import pytest

from health_tech_research_agent import research_runner as rr
from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# 1. Prompt fidelity — band schema + stage-aware cutpoints + the fence.
# ---------------------------------------------------------------------------

def _prompt(stage="series-a"):
    return rr.build_growth_extractor_prompt("ACME Health", "EVIDENCE", stage)


def test_prompt_builds_and_substitutes():
    p = _prompt()
    assert "Company: ACME Health" in p and "EVIDENCE" in p
    assert '{"growth_band"' in p                      # v1.24 band schema
    assert "{{" not in p and "}}" not in p


def test_prompt_injects_stage_scale_b_cutpoints():
    # series-a Scale B: score-8 = 200 (HIGH cutpoint), score-5 = 100 (SOLID floor).
    p = _prompt("series-a")
    assert "(series-a)" in p
    assert "200%" in p and "100%" in p
    # series-d-plus maps to the PUBLIC row: score-8 = 62, score-5 = 35.
    pub = _prompt("series-d-plus")
    assert "(public)" in pub and "62%" in pub and "35%" in pub


def test_prompt_classifies_never_derives():
    p = _prompt()
    assert "You CLASSIFY into a band; you do NOT compute or combine numbers" in p
    assert "NEVER combine two DIFFERENT sources into a rate" in p
    assert '"growth_band": "high" | "solid" | "slow" | "unknown"' in p


def test_prompt_keeps_the_b6_1_fence():
    p = _prompt()
    assert "NEVER band on a count" in p
    assert "do NOT manufacture growth" in p


# ---------------------------------------------------------------------------
# 2. Parse / normalize — the band read {growth_band, evidence}.
# ---------------------------------------------------------------------------

def test_normalize_folds_band_and_keeps_evidence():
    read = se.normalize_growth_read({"growth_band": "HIGH", "evidence": "450% YoY (company-reported)"})
    assert read["growth_band"] == "high"
    assert read["evidence"] == "450% YoY (company-reported)"


def test_unrecognized_or_missing_band_falls_to_unknown():
    assert se.normalize_growth_read({"growth_band": "vibes"})["growth_band"] == "unknown"
    assert se.normalize_growth_read({})["growth_band"] == "unknown"
    assert se.normalize_growth_read(None)["growth_band"] == "unknown"


def test_flatten_growth_read_columns():
    parsed = {"growth_read": {"growth_band": "solid", "evidence": "35% YoY (Latka)"}}
    cols = se.flatten_growth_read(parsed)
    assert cols["growth_band"] == "solid"
    assert cols["growth_evidence"] == "35% YoY (Latka)"
    assert se.flatten_growth_read({"company": "x"})["growth_band"] == "unknown"
    assert se.GROWTH_READ_FIELDS == ["growth_band", "growth_evidence"]


# ---------------------------------------------------------------------------
# 3. SCORE INTEGRATION — band -> score (stage-independent; the phase-relativity is in the band).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("band,expected", [("high", 9), ("solid", 6), ("slow", 3), ("unknown", 4)])
def test_band_maps_to_fixed_score(band, expected):
    read = se.normalize_growth_read({"growth_band": band, "evidence": "x"})
    score, note = se.score_growth(read, "series-c")
    assert score == expected
    assert band in note


def test_growth_is_never_none_now():
    # the v1.23 'absent -> None -> cap' path is gone: any read yields a band score (UNKNOWN=4 at worst).
    score, _ = se.score_growth(se.normalize_growth_read({}), "series-b")
    assert score == 4


def test_fenced_count_only_company_bands_unknown_not_a_leaked_rate():
    # a count-only company that the extractor correctly fences -> unknown=4 (neutral), never a fabricated high.
    read = se.normalize_growth_read({"growth_band": "unknown", "evidence": "only covered-lives growth (fenced)"})
    score, _ = se.score_growth(read, "series-c")
    assert score == 4


# ---------------------------------------------------------------------------
# 4. BAND-vs-SCALE-B ±2 VALIDATION — the bands preserve the retired Scale-B interpolation's intent.
#    Named anchors from SOT §B6 v1.24 (rate %, stage -> expected band).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,rate,stage,expected_band", [
    ("hinge", 51, "public", "solid"),
    ("function", 450, "series-b", "high"),
    ("rula", 100, "series-c", "high"),
    ("maven", 26, "series-d-plus", "slow"),
    ("transcarent", 35, "series-d-plus", "solid"),
])
def test_band_for_rate_matches_anchor_and_within_2_of_scale_b(name, rate, stage, expected_band):
    band = se.band_for_rate(rate, stage)
    assert band == expected_band, f"{name}: {rate}%@{stage} -> {band} (expected {expected_band})"
    band_score = se.GROWTH_BAND_SCORE[band]
    interp = se.scale_interp(rate, se.GROWTH_SCALE[se._growth_stage(stage)])
    assert abs(band_score - interp) <= 2, f"{name}: band {band_score} vs Scale-B interp {interp} (>2 apart)"
