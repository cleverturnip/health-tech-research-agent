"""Tests for Slice 2 deterministic derivations (structured_evidence.py).

The audit cases are the proof:
- Function Health (series-b + large revenue) -> early-growth, never late-stage; and
  credible-estimate revenue + growing paying base + q3=no -> commercial signal 3.
- Solace (q3 funding-dependent, thin real traction) -> capped below strong, never 3.
"""

import pytest

from health_tech_research_agent import structured_evidence as se
from health_tech_research_agent.candidate_priority import signal_text_to_score


# ---------------------------------------------------------------------------
# derive_maturity — funding stage anchors; revenue NEVER touches it
# ---------------------------------------------------------------------------


def test_maturity_function_health_series_b_is_early_growth():
    label, needs_review = se.derive_maturity({"funding_stage": "series-b", "ipo_status": "private"})
    assert label == "early-growth"
    assert needs_review is False


def test_maturity_ignores_revenue_and_valuation():
    """The Function fix: a Series B with hypergrowth revenue stays early-growth.
    Revenue/ARR/valuation/total_funding must not move the label."""
    row = {
        "funding_stage": "series-b",
        "ipo_status": "private",
        "revenue_or_arr": "$100M ARR (Sacra, 2025)",
        "total_funding": "$250M",
        "last_raise_amount": "$53M",
        "growth_signal": "growing fast",
    }
    label, _ = se.derive_maturity(row)
    assert label == "early-growth"  # NOT late-stage


@pytest.mark.parametrize(
    "stage, expected",
    [
        ("series-d-plus", "late-stage"),
        ("series-c", "scale-up"),
        ("series-b", "early-growth"),
        ("series-a", "early-growth"),
        ("seed", "early"),
        ("pre-seed", "early"),
        ("public", "public"),
    ],
)
def test_maturity_table(stage, expected):
    label, needs_review = se.derive_maturity({"funding_stage": stage, "ipo_status": "private"})
    assert label == expected
    assert needs_review is False


def test_maturity_ipo_filed_is_near_ipo():
    # S-1 filed but not yet trading -> near-ipo, regardless of last priced round.
    label, needs_review = se.derive_maturity({"funding_stage": "series-c", "ipo_status": "filed"})
    assert label == "near-ipo"
    assert needs_review is False


def test_maturity_ipo_public_overrides_stage():
    label, _ = se.derive_maturity({"funding_stage": "series-b", "ipo_status": "public"})
    assert label == "public"


def test_maturity_unknown_flags_for_review():
    for row in ({"funding_stage": "unknown", "ipo_status": "private"},
                {"funding_stage": "", "ipo_status": ""},
                {}):
        label, needs_review = se.derive_maturity(row)
        assert label == "unclear"
        assert needs_review is True


def test_maturity_normalizes_input_variants():
    assert se.derive_maturity({"funding_stage": "Series B"})[0] == "early-growth"
    assert se.derive_maturity({"funding_stage": "series D+"})[0] == "late-stage"
    assert se.derive_maturity({"funding_stage": "Series E"})[0] == "late-stage"
    assert se.derive_maturity({"funding_stage": "Pre-Seed"})[0] == "early"
    assert se.derive_maturity({"ipo_status": "Public"})[0] == "public"


# ---------------------------------------------------------------------------
# derive_commercial_signal — facts + four red-flags -> 0-3; funding excluded
# ---------------------------------------------------------------------------


def _commercial_row(**over):
    base = {
        "revenue_or_arr": "",
        "paying_customer_count": "",
        "q1_acquisition": "flat",
        "q2_monetization": "typical",
        "q3_funding_dependent": "no",
        "q4_evidence_quality": "company-reported",
    }
    base.update(over)
    return base


def test_commercial_function_credible_estimate_is_strong():
    """Function: Sacra-estimated revenue + growing paying base + not funding-dependent
    -> strong (credible estimates support strong)."""
    row = _commercial_row(
        revenue_or_arr="~$100M ARR (Sacra estimate, 2025)",
        paying_customer_count="~200k paying members",
        q1_acquisition="growing",
        q2_monetization="strong",
        q3_funding_dependent="no",
        q4_evidence_quality="credible-estimate",
    )
    assert se.derive_commercial_signal(row) == 3


def test_commercial_solace_funding_dependent_capped_below_strong():
    """Solace: funding-dependent (q3=yes) -> never strong, even when the other signals
    would otherwise qualify. q3 is the hard ceiling."""
    row = _commercial_row(
        revenue_or_arr="some early revenue",      # real traction present...
        q1_acquisition="growing",
        q2_monetization="strong",
        q4_evidence_quality="credible-estimate",
        q3_funding_dependent="yes",               # ...but the story rests on the raise
    )
    score = se.derive_commercial_signal(row)
    assert score < 3
    assert score == 2  # funding-dependent + real traction -> moderate ceiling


def test_commercial_solace_funding_dependent_negligible_is_weak():
    row = _commercial_row(
        revenue_or_arr="",            # negligible real commercial evidence
        paying_customer_count="",
        q1_acquisition="flat",
        q2_monetization="weak",
        q3_funding_dependent="yes",
    )
    assert se.derive_commercial_signal(row) == 1


def test_commercial_would_be_strong_but_promotional_is_capped_at_moderate():
    row = _commercial_row(
        revenue_or_arr="claims of fast growth",
        paying_customer_count="lots of users (marketing page)",
        q1_acquisition="growing",
        q2_monetization="strong",
        q3_funding_dependent="no",
        q4_evidence_quality="unverified-promotional",   # q4 cap
    )
    assert se.derive_commercial_signal(row) == 2


def test_commercial_trap_declining_and_weak_is_weak():
    row = _commercial_row(
        revenue_or_arr="declining revenue",
        q1_acquisition="declining",
        q2_monetization="weak",
        q3_funding_dependent="no",
    )
    assert se.derive_commercial_signal(row) == 1


def test_commercial_funding_dependent_with_real_traction_is_moderate():
    row = _commercial_row(
        revenue_or_arr="modest ARR reported",
        q1_acquisition="flat",
        q2_monetization="typical",
        q3_funding_dependent="yes",
    )
    assert se.derive_commercial_signal(row) == 2


def test_commercial_no_evidence_is_none():
    row = _commercial_row(
        revenue_or_arr="",
        paying_customer_count="none",
        q1_acquisition="",
        q2_monetization="",
        q3_funding_dependent="no",
    )
    assert se.derive_commercial_signal(row) == 0


def test_commercial_strong_via_high_revenue_per_user():
    # q2=strong is a genuine traction strength on its own (rev-per-user path).
    row = _commercial_row(
        revenue_or_arr="reported ARR",
        q1_acquisition="flat",
        q2_monetization="strong",
        q3_funding_dependent="no",
        q4_evidence_quality="company-reported",
    )
    assert se.derive_commercial_signal(row) == 3


def test_commercial_real_but_no_standout_is_moderate():
    row = _commercial_row(
        revenue_or_arr="real reported revenue",
        q1_acquisition="flat",
        q2_monetization="typical",
        q3_funding_dependent="no",
    )
    assert se.derive_commercial_signal(row) == 2


def test_commercial_v1_presence_based_not_parsed_counts():
    """v1 reading: presence of real evidence (no parsed number) is enough to be real
    traction -> moderate, not none/weak. Size boundary is deferred to calibration."""
    row = _commercial_row(
        revenue_or_arr="has paying subscribers; figure not disclosed",
        q1_acquisition="flat",
        q2_monetization="typical",
        q3_funding_dependent="no",
    )
    assert se.derive_commercial_signal(row) == 2


def test_commercial_q4_space_variant_normalized():
    row = _commercial_row(
        revenue_or_arr="reported ARR",
        q1_acquisition="growing",
        q2_monetization="strong",
        q3_funding_dependent="no",
        q4_evidence_quality="Credible Estimate",   # space + caps -> credible-estimate
    )
    assert se.derive_commercial_signal(row) == 3


# ---------------------------------------------------------------------------
# 0-3 <-> text round-trips with the engine's reader
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score, text", [(3, "strong"), (2, "moderate"), (1, "weak"), (0, "none")])
def test_commercial_signal_text_roundtrips_with_engine(score, text):
    assert se.commercial_signal_to_text(score) == text
    assert signal_text_to_score(text) == score


# ---------------------------------------------------------------------------
# flatten_slice2_fields
# ---------------------------------------------------------------------------


def test_flatten_extracts_all_fields():
    parsed = {
        "maturity_evidence": {
            "funding_stage": "series-b", "ipo_status": "private", "founding_year": "2019",
            "total_funding": "$250M", "funding_stage_evidence": "Crunchbase 2025",
        },
        "commercial_evidence": {
            "revenue_or_arr": "$100M (Sacra)", "paying_customer_count": "200k",
            "q1_acquisition": "growing", "q2_monetization": "strong",
            "q3_funding_dependent": "no", "q4_evidence_quality": "credible-estimate",
        },
    }
    flat = se.flatten_slice2_fields(parsed)
    # every declared column present
    for field in se.MATURITY_EVIDENCE_FIELDS + se.COMMERCIAL_EVIDENCE_FIELDS:
        assert field in flat
    assert flat["funding_stage"] == "series-b"
    assert flat["q3_funding_dependent"] == "no"
    assert flat["revenue_or_arr"] == "$100M (Sacra)"
    # absent sub-fields become empty strings, not missing keys
    assert flat["ipo_or_filing_date"] == ""
    assert flat["business_model_type"] == ""


def test_flatten_missing_or_nondict_blocks_yield_empty_strings():
    for parsed in ({}, {"maturity_evidence": None, "commercial_evidence": "oops"}, "not-a-dict"):
        flat = se.flatten_slice2_fields(parsed)
        assert set(flat) == set(se.MATURITY_EVIDENCE_FIELDS + se.COMMERCIAL_EVIDENCE_FIELDS)
        assert all(value == "" for value in flat.values())


def test_flatten_and_derive_compose():
    """flatten -> derive on the flattened row reproduces the expected label/signal."""
    parsed = {
        "maturity_evidence": {"funding_stage": "series-b", "ipo_status": "private"},
        "commercial_evidence": {
            "revenue_or_arr": "$100M (Sacra)", "paying_customer_count": "200k",
            "q1_acquisition": "growing", "q2_monetization": "strong",
            "q3_funding_dependent": "no", "q4_evidence_quality": "credible-estimate",
        },
    }
    flat = se.flatten_slice2_fields(parsed)
    assert se.derive_maturity(flat) == ("early-growth", False)
    assert se.derive_commercial_signal(flat) == 3
