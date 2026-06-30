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
    assert '{"kind"' in p
    assert "{{" not in p and "}}" not in p


def test_prompt_has_the_b6_1_fence():
    p = _prompt()
    assert "NEVER emit a count's growth as rate_pct" in p
    assert "A fenced count is not a fallback for a missing revenue rate" in p


def test_prompt_has_the_hard_3_condition_derive_gate():
    # v1.18: the same-source guard is a HARD all-three-or-no-derive gate (not a soft caveat).
    p = _prompt()
    assert "A DERIVE IS VALID ONLY IF ALL THREE HOLD" in p
    assert "(1) SAME MEASURE" in p
    assert "(2) SAME SOURCE" in p
    assert "(3) CORRECT TIME ORDER" in p
    assert "TWO DIFFERENT estimators" in p                          # the load-bearing same-source line
    assert "$8.0M revenue in 2022 -> $12.3M in 2023" in p            # season good-derive (one estimator's series)
    assert "does NOT block a derive that meets (1)-(3)" in p          # hedge doesn't block a passing derive


def test_prompt_has_the_determinate_qualitative_vs_absent_rule():
    p = _prompt()
    assert "DETERMINATE, decided by ONE test" in p
    assert "affirmative statement about REVENUE direction" in p


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
