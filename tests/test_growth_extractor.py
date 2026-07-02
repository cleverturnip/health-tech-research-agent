"""§B6 v1.24/v1.25 — deterministic tests for the BAND-CLASSIFICATION growth extractor (signed-off wording).

The extractor is LLM-facing; its LIVE validation is the Colab R1 run. Offline here:
  1. PROMPT FIDELITY — the band + basis + source-mode schema, the STAGE-AWARE Scale-B cutpoints, the v1.25
     trajectory-magnitude rule (complementary-multi allowed) and the HARD fence are byte-faithful.
  2. PARSE — normalize_growth_read / flatten_growth_read (band/basis/source_mode; malformed -> unknown).
  3. SCORE INTEGRATION — score_growth maps band -> score (HIGH=9 / SOLID=6 / SLOW=3 / UNKNOWN=4), and the
     v1.25 FENCE BACKSTOP forces UNKNOWN when the basis is counts-scale / none (pomelo).
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


def test_prompt_bands_on_trajectory_magnitude_complementary_multi_allowed():
    # v1.25: the WRONG "never combine two sources" rule is GONE; complementary-multi is allowed, only a
    # genuine same-period CONFLICT is refused.
    p = _prompt()
    assert "You CLASSIFY into a band; you do NOT compute a precise rate" in p
    assert "NEVER combine two DIFFERENT sources into a rate" not in p     # the wrong rule is removed
    assert "COMPLEMENTARY revenue points from DIFFERENT sources/years" in p
    assert "REFUSE only a genuine CONFLICT" in p
    assert "TRAJECTORY MAGNITUDE" in p


def test_prompt_emits_basis_and_source_mode_schema():
    p = _prompt()
    assert '"growth_band": "high" | "solid" | "slow" | "unknown"' in p
    assert '"growth_basis": "revenue-rate" | "revenue-trajectory" | "counts-scale" | "none"' in p
    assert '"source_mode": "single-source" | "complementary-multi" | "conflict" | "none"' in p


def test_prompt_hard_fence_counts_to_unknown():
    p = _prompt()
    assert "NEVER band HIGH/SOLID on counts" in p
    assert 'the band is "unknown" and "growth_basis" is "counts-scale"' in p
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


def test_normalize_carries_basis_and_source_mode():
    read = se.normalize_growth_read({"growth_band": "high", "growth_basis": "revenue-trajectory",
                                     "source_mode": "complementary-multi", "evidence": "x"})
    assert read["growth_basis"] == "revenue-trajectory"
    assert read["source_mode"] == "complementary-multi"
    # unrecognized basis / mode -> '' (NOT fenced; back-compat)
    loose = se.normalize_growth_read({"growth_band": "high", "growth_basis": "vibes"})
    assert loose["growth_basis"] == "" and loose["source_mode"] == ""


def test_flatten_growth_read_columns():
    parsed = {"growth_read": {"growth_band": "solid", "growth_basis": "revenue-rate",
                              "source_mode": "single-source", "evidence": "35% YoY (Latka)"}}
    cols = se.flatten_growth_read(parsed)
    assert cols["growth_band"] == "solid"
    assert cols["growth_basis"] == "revenue-rate"
    assert cols["growth_source_mode"] == "single-source"
    assert cols["growth_evidence"] == "35% YoY (Latka)"
    assert se.flatten_growth_read({"company": "x"})["growth_band"] == "unknown"
    assert se.GROWTH_READ_FIELDS == ["growth_band", "growth_basis", "growth_source_mode", "growth_evidence"]


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
# 3b. v1.25 FENCE BACKSTOP (gate-in-code) + complementary-multi allowed.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("basis", ["counts-scale", "none"])
def test_fence_backstop_forces_unknown_even_if_llm_bands_high(basis):
    # pomelo case: the LLM banded HIGH but its OWN basis says counts/none -> code FORCES UNKNOWN=4.
    read = se.normalize_growth_read({"growth_band": "high", "growth_basis": basis,
                                     "evidence": "covered-lives / member scale expansion"})
    score, note = se.score_growth(read, "series-c")
    assert score == 4
    assert "FENCED" in note


def test_revenue_basis_bands_are_honored():
    # a HIGH band resting on a real revenue basis is NOT fenced (equip/bicycle complementary-multi trajectory).
    for basis, mode in [("revenue-rate", "single-source"), ("revenue-trajectory", "complementary-multi")]:
        read = se.normalize_growth_read({"growth_band": "high", "growth_basis": basis, "source_mode": mode,
                                         "evidence": "$4.5M-2021 (Latka) + $35M-2023 (CB Insights)"})
        score, note = se.score_growth(read, "series-c")
        assert score == 9 and "FENCED" not in note


def test_absent_basis_is_not_fenced_backcompat():
    # a read with NO basis (old-style / a test) is honored, not fenced (back-compat).
    score, note = se.score_growth({"growth_band": "high", "evidence": "x"}, "series-c")
    assert score == 9 and "FENCED" not in note


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
