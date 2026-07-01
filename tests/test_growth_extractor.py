"""Commit 5b — deterministic tests for the §B6/§B6.1 LLM growth extractor (signed-off wording).

The extractor is LLM-facing; its LIVE validation over the 3 R2 cases is the Colab run. Offline here:
  1. PROMPT FIDELITY — the signed wording (the fence + the same-measure derive guard + the determinate
     qualitative-vs-absent rule) is byte-faithful in the production prompt.
  2. PARSE — normalize_growth_read / flatten_growth_read (kind normalization; malformed -> absent).
  3. SCORE INTEGRATION — the PINNED R2 reads, scored via score_growth: pomelo/outcomes4me qualitative
     "growing" -> 5; season rate 53.7 @ series-a -> 3 (the documented grw 5->3 under the R2 fix).
"""

import pytest

from health_tech_research_agent import research_runner as rr
from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# 1. Prompt fidelity — the signed wording (both closed gaps) is in the production prompt.
# ---------------------------------------------------------------------------

def _prompt():
    return rr.build_growth_extractor_prompt("ACME Health", "EVIDENCE")


def test_prompt_builds_and_substitutes():
    p = _prompt()
    assert "Company: ACME Health" in p and "EVIDENCE" in p
    assert '{"figures"' in p                       # v1.22 report-figures schema
    assert "{{" not in p and "}}" not in p


def test_prompt_reports_figures_does_not_derive():
    # v1.22 (SIGNED): the extractor REPORTS figures with per-figure source; the code derives.
    p = _prompt()
    assert "REPORT the dated revenue figures you find -- NOT to compute a growth rate" in p
    assert "DO NOT derive, combine, or reconcile figures" in p
    assert '"source": "<the NAMED publisher' in p   # per-figure source (what the backstop needs)
    assert '"measure": "revenue" | "arr"' in p


def test_prompt_keeps_the_b6_1_fence():
    p = _prompt()
    assert "NEVER put a count in figures" in p
    assert "Do NOT manufacture revenue" in p


# ---------------------------------------------------------------------------
# 2. Parse / normalize
# ---------------------------------------------------------------------------

def test_normalize_folds_kind_and_parses_numbers():
    read = se.normalize_growth_read({"kind": "zero_baseline", "magnitude_usd_m": "112", "source": "Derived"})
    assert read["kind"] == "zero-baseline"        # '_' folded to '-'
    assert read["magnitude_usd_m"] == 112.0
    assert read["source"] == "derived"


def test_unrecognized_kind_falls_to_absent():
    assert se.normalize_growth_read({"kind": "vibes"})["kind"] == "absent"
    assert se.normalize_growth_read({})["kind"] == "absent"


def test_flatten_growth_read_columns():
    parsed = {"growth_read": {"kind": "rate", "rate_pct": 53.7, "source": "derived",
                              "basis": "$8.0M 2022 -> $12.3M 2023"}}
    cols = se.flatten_growth_read(parsed)
    assert cols["growth_kind"] == "rate"
    assert cols["growth_rate_pct"] == 53.7
    assert cols["growth_source"] == "derived"
    assert cols["growth_basis"] == "$8.0M 2022 -> $12.3M 2023"
    assert se.flatten_growth_read({"company": "x"})["growth_kind"] == "absent"


# ---------------------------------------------------------------------------
# 3. SCORE INTEGRATION — the PINNED R2 reads -> score_growth (extractor read -> deterministic score).
# ---------------------------------------------------------------------------

def test_pomelo_pinned_read_scores_qualitative_5():
    # pomelo: covered-lives fenced + Latka/Growjo derive blocked -> "growing" (affirmative revenue dir).
    read = se.normalize_growth_read({"kind": "qualitative", "qualitative": "growing"})
    score, _ = se.score_growth(read, "series-c")
    assert score == 5


def test_outcomes4me_pinned_read_scores_qualitative_5():
    read = se.normalize_growth_read({"kind": "qualitative", "qualitative": "growing"})
    score, _ = se.score_growth(read, "series-b")
    assert score == 5


def test_season_pinned_read_scores_rate_3_at_series_a():
    # season: the FOUND buried rate $8M->$12.3M = 53.7% at series-a -> Scale B -> 3.
    # DOCUMENTED R2 effect: grw 5 (spike qualitative fallback) -> 3 (the real rate). R1 expects 3.
    read = se.normalize_growth_read({"kind": "rate", "rate_pct": 53.7, "source": "derived"})
    score, note = se.score_growth(read, "series-a")
    assert score == 3
    assert "53.7%@series-a" in note


def test_a_fenced_count_read_as_absent_does_not_score_a_rate():
    # if the extractor correctly fences a count-only company -> absent -> None (cap@7), never a leaked rate.
    read = se.normalize_growth_read({"kind": "absent", "basis": "only covered-lives growth (fenced)"})
    score, _ = se.score_growth(read, "series-c")
    assert score is None


# ---------------------------------------------------------------------------
# 4. Fix 2 (v1.22) — the DETERMINISTIC same-source derive backstop (extractor reports; code derives).
# ---------------------------------------------------------------------------

def test_equip_cross_source_figures_refuse_derive_qualitative():
    # equip: Latka 2021 + CB Insights 2023 = TWO publishers -> code REFUSES the cross-source derive -> the
    # 7.8x can no longer be manufactured. (The exact frozen-wrong read that put equip at P1.)
    read = se.normalize_growth_read({"figures": [
        {"value_usd_m": 4.5, "year": 2021, "source": "Latka", "measure": "revenue"},
        {"value_usd_m": 35, "year": 2023, "source": "CB Insights financials", "measure": "revenue"}]})
    assert read["kind"] == "absent"          # no same-source series, no qualitative -> absent (not a rate)
    assert read["rate_pct"] is None


def test_same_source_series_derives_the_rate():
    # one estimator's OWN dated series -> a valid derive (season-style $8M->$12.3M)
    read = se.normalize_growth_read({"figures": [
        {"value_usd_m": 8.0, "year": 2022, "source": "Latka", "measure": "revenue"},
        {"value_usd_m": 12.3, "year": 2023, "source": "Latka", "measure": "revenue"}]})
    assert read["kind"] == "rate"
    assert round(read["rate_pct"], 1) == 53.8   # (12.3/8 - 1)*100


def test_source_aliases_treated_same_publisher_variants_differ():
    # "CB Insights" == "CB Insights financials" (same publisher, derive) ...
    same = se.normalize_growth_read({"figures": [
        {"value_usd_m": 10, "year": 2022, "source": "CB Insights", "measure": "revenue"},
        {"value_usd_m": 20, "year": 2023, "source": "CB Insights financials page", "measure": "revenue"}]})
    assert same["kind"] == "rate"
    # ... but two DIFFERENT publishers do NOT derive
    diff = se.normalize_growth_read({"figures": [
        {"value_usd_m": 10, "year": 2022, "source": "Growjo", "measure": "revenue"},
        {"value_usd_m": 20, "year": 2023, "source": "Sacra", "measure": "revenue"}], "qualitative": "growing"})
    assert diff["kind"] == "qualitative"


def test_figures_qualitative_and_zero_baseline_fallbacks():
    assert se.normalize_growth_read({"figures": [], "qualitative": "growing"})["kind"] == "qualitative"
    assert se.normalize_growth_read({"figures": []})["kind"] == "absent"
    zb = se.normalize_growth_read({"figures": [], "zero_baseline_usd_m": 40})
    assert zb["kind"] == "zero-baseline" and zb["magnitude_usd_m"] == 40.0


def test_legacy_schema_still_normalizes():
    # the checkpoint's stored reads (no 'figures') still parse via the legacy path
    read = se.normalize_growth_read({"kind": "rate", "rate_pct": 53.7, "source": "derived"})
    assert read["kind"] == "rate" and read["rate_pct"] == 53.7
