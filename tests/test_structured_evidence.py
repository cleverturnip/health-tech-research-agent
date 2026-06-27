"""Tests for Slice 2 deterministic derivations (structured_evidence.py).

The audit cases are the proof:
- Function Health (series-b + large revenue) -> early-growth, never late-stage; and
  credible-estimate revenue + growing paying base + q3=no -> commercial signal 3.
- Solace (q3 funding-dependent, thin real traction) -> capped below strong, never 3.
"""

import json

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
            "funding_rounds": [
                {"type": "series-a", "date": "2020", "amount": "$10M", "is_priced_equity": True},
                {"type": "series-b", "date": "2022", "amount": "$30M", "is_priced_equity": True},
            ],
            "ipo_event": {"occurred": False},
            "ipo_status": "private", "founding_year": "2019",
            "total_funding": "$250M", "funding_stage_evidence": "Crunchbase 2025",
        },
        "commercial_evidence": {
            "revenue_or_arr": "$100M (Sacra)", "paying_customer_count": "200k",
            "user_scale_signal": "~2M registered users (2024)",
            "q1_acquisition": "growing", "q2_monetization": "strong",
            "q3_funding_dependent": "no", "q4_evidence_quality": "credible-estimate",
        },
    }
    flat = se.flatten_slice2_fields(parsed)
    # every declared column present
    for field in se.MATURITY_EVIDENCE_FIELDS + se.COMMERCIAL_EVIDENCE_FIELDS:
        assert field in flat
    assert flat["funding_stage"] == "series-b"           # DERIVED by the mapper (latest priced round)
    assert "series-b" in flat["funding_rounds_json"]     # raw rounds persisted (recomputable)
    assert flat["q3_funding_dependent"] == "no"
    assert flat["revenue_or_arr"] == "$100M (Sacra)"
    assert flat["user_scale_signal"] == "~2M registered users (2024)"   # secondary signal persisted
    # absent sub-fields become empty strings, not missing keys
    assert flat["ipo_or_filing_date"] == ""
    assert flat["business_model_type"] == ""


def test_flatten_missing_or_nondict_blocks_yield_empty_strings():
    for parsed in ({}, {"maturity_evidence": None, "commercial_evidence": "oops"}, "not-a-dict"):
        flat = se.flatten_slice2_fields(parsed)
        assert set(flat) == set(se.MATURITY_EVIDENCE_FIELDS + se.COMMERCIAL_EVIDENCE_FIELDS)
        # funding_stage is mapper-derived: no rounds -> "unknown"; every other field empty
        assert flat["funding_stage"] == "unknown"
        assert all(v == "" for k, v in flat.items() if k != "funding_stage")


def test_flatten_and_derive_compose():
    """flatten -> derive on the flattened row reproduces the expected label/signal."""
    parsed = {
        "maturity_evidence": {
            "funding_rounds": [{"type": "series-b", "date": "2022", "is_priced_equity": True}],
            "ipo_event": {"occurred": False}, "ipo_status": "private",
        },
        "commercial_evidence": {
            "revenue_or_arr": "$100M (Sacra)", "paying_customer_count": "200k",
            "q1_acquisition": "growing", "q2_monetization": "strong",
            "q3_funding_dependent": "no", "q4_evidence_quality": "credible-estimate",
        },
    }
    flat = se.flatten_slice2_fields(parsed)
    assert se.derive_maturity(flat) == ("early-growth", False)
    assert se.derive_commercial_signal(flat) == 3


def test_funding_stage_mapper():
    """The deterministic Rule-7 mapper -- the whole selection logic validated offline (zero credits)."""
    sword = [{"type": "series-a", "date": "2019", "is_priced_equity": True},
             {"type": "series-b", "date": "2020", "is_priced_equity": True},
             {"type": "series-c", "date": "2021", "is_priced_equity": True},
             {"type": "series-d", "date": "2021-11", "is_priced_equity": True}]
    assert se.funding_stage_from_rounds(sword, {"occurred": False}) == "series-d-plus"   # latest priced = D
    allara = [{"type": "seed", "date": "2021", "is_priced_equity": True},
              {"type": "series-a", "date": "2022", "is_priced_equity": True},
              {"type": "series-b", "date": "2023", "is_priced_equity": True}]
    assert se.funding_stage_from_rounds(allara, {"occurred": False}) == "series-b"        # control -> B
    assert se.funding_stage_from_rounds(allara, {"occurred": True, "date": "2025-05"}) == "public"  # IPO outranks
    bridge_after_c = [{"type": "series-c", "date": "2022", "is_priced_equity": True},
                      {"type": "bridge", "date": "2024", "is_priced_equity": False}]
    assert se.funding_stage_from_rounds(bridge_after_c, {"occurred": False}) == "series-c"  # bridge != new bucket
    assert se.funding_stage_from_rounds(
        [{"type": "series-b", "date": "unknown", "is_priced_equity": True}], {"occurred": False}) == "unknown"
    assert se.funding_stage_from_rounds([], {"occurred": False}) == "unknown"              # empty
    # Tightening 1: seed-only -> the too-early bucket "seed" (gate FAIL), NOT a generic pass
    assert se.funding_stage_from_rounds(
        [{"type": "seed", "date": "2023", "is_priced_equity": True}], {"occurred": False}) == "seed"
    # Tightening 2: same-year tie (C 2021 + D 2021) -> later stage wins -> series-d-plus
    assert se.funding_stage_from_rounds(
        [{"type": "series-c", "date": "2021", "is_priced_equity": True},
         {"type": "series-d", "date": "2021", "is_priced_equity": True}], {"occurred": False}) == "series-d-plus"
    # tolerates the LLM emitting string booleans ("true"/"false")
    assert se.funding_stage_from_rounds(
        [{"type": "series-b", "date": "2022", "is_priced_equity": "true"}], {"occurred": "false"}) == "series-b"


def test_funding_stage_failsafe_flag():
    """Gate fail-safe (req 1): fires on ABSENT recent-round + inconsistency, NEVER on ABSENT alone."""
    # a recent round WAS gathered -> never flags, whatever the stage / age / scale
    assert se.funding_stage_needs_review("series-b", True, company_age_years=20, commercial_signal=3) is False
    # ABSENT alone (quiet-but-healthy: early, young, no scale) -> NOT flagged
    assert se.funding_stage_needs_review("series-b", False, company_age_years=3, commercial_signal=0) is False
    # ABSENT + early + OLD -> flagged (an 8-yr-old company reading series-b is inconsistent)
    assert se.funding_stage_needs_review("series-b", False, company_age_years=8, commercial_signal=0) is True
    # ABSENT + early + SCALED -> flagged (strong commercial signal but reads early)
    assert se.funding_stage_needs_review("series-a", False, company_age_years=2, commercial_signal=2) is True
    # ABSENT but NOT early (D+/public already FAIL the gate) -> never flags (no false-pass risk)
    assert se.funding_stage_needs_review("series-d-plus", False, company_age_years=20, commercial_signal=3) is False
    assert se.funding_stage_needs_review("public", False, company_age_years=20, commercial_signal=3) is False
    # string-bool tolerance (the recall signal may arrive as a stored string)
    assert se.funding_stage_needs_review("series-b", "True", company_age_years=20, commercial_signal=3) is False


def test_has_recent_priced_round():
    recent = [{"type": "series-b", "date": "2024", "is_priced_equity": True},
              {"type": "series-a", "date": "2019", "is_priced_equity": True}]
    assert se._has_recent_priced_round(recent, 2026) is True       # series-b 2024 within ~2y of 2026
    assert se._has_recent_priced_round(
        [{"type": "series-b", "date": "2019", "is_priced_equity": True}], 2026) is False   # 2019 not recent
    assert se._has_recent_priced_round(
        [{"type": "bridge", "date": "2025", "is_priced_equity": False}], 2026) is False    # bridge isn't priced
    assert se._has_recent_priced_round([], 2026) is False


def test_derive_funding_failsafe_recomputes_from_row():
    # an OLD company (founded 2014) reading series-b with NO recent priced round -> flag for review
    base = {"funding_stage": "series-b", "founding_year": "2014",
            "revenue_or_arr": "", "q1_acquisition": "", "q2_monetization": "",
            "q3_funding_dependent": "", "paying_customer_count": "", "q4_evidence_quality": ""}
    stale = dict(base, funding_rounds_json=json.dumps(
        [{"type": "series-b", "date": "2017", "is_priced_equity": True}]))
    assert se.derive_funding_failsafe(stale, ref_year=2026) is True
    # same company but WITH a recent (2025) round gathered -> no flag (recall not missed)
    fresh = dict(base, funding_rounds_json=json.dumps(
        [{"type": "series-b", "date": "2025", "is_priced_equity": True}]))
    assert se.derive_funding_failsafe(fresh, ref_year=2026) is False


# ---------------------------------------------------------------------------
# derive_reset_signal (Slice 3.5 multi-event) — per-event opening evaluation
# ---------------------------------------------------------------------------


def _ev(event_type, opening, basis=""):
    return {"event_type": event_type, "basis": basis, "creates_high_agency_opening": opening}


def _reset(*events):
    """Live reset_evidence dict carrying a reset_events list."""
    return {"reset_events": list(events)}


def test_reset_zoe_multi_event_fires_on_restructuring():
    # THE proof for 3.5: a coexisting restructuring's "yes" is not buried by a louder pivot's "no".
    zoe = _reset(_ev("strategic-pivot", "no"), _ev("restructuring-layoffs", "yes"))
    assert se.derive_reset_signal(zoe) is True


def test_reset_noom_strategic_pivot_never_fires():
    assert se.derive_reset_signal(_reset(_ev("strategic-pivot", "yes"))) is False


def test_reset_single_recognized_event_fires():
    assert se.derive_reset_signal(_reset(_ev("leadership-change", "yes"))) is True
    assert se.derive_reset_signal(_reset(_ev("declared-transformation", "yes"))) is True


def test_reset_empty_list_is_false():
    assert se.derive_reset_signal(_reset()) is False
    assert se.derive_reset_signal({}) is False


def test_reset_multiple_never_fire_only_is_false():
    assert se.derive_reset_signal(
        _reset(_ev("strategic-pivot", "yes"), _ev("ma-integration", "yes"))
    ) is False


def test_reset_mixed_pivot_no_plus_leadership_yes_fires():
    assert se.derive_reset_signal(
        _reset(_ev("strategic-pivot", "no"), _ev("leadership-change", "yes"))
    ) is True


def test_reset_restructuring_layoffs_rides_the_opening_question():
    assert se.derive_reset_signal(_reset(_ev("restructuring-layoffs", "yes"))) is True
    assert se.derive_reset_signal(_reset(_ev("restructuring-layoffs", "no"))) is False


def test_reset_ma_integration_never_fires_incl_ampersand_variant():
    assert se.derive_reset_signal(_reset(_ev("ma-integration", "yes"))) is False
    assert se.derive_reset_signal(_reset(_ev("M&A integration", "yes"))) is False  # normalizes


def test_reset_opening_no_or_unclear_is_false():
    assert se.derive_reset_signal(_reset(_ev("leadership-change", "no"))) is False
    assert se.derive_reset_signal(_reset(_ev("leadership-change", "unclear"))) is False


def test_reset_normalizes_input_variants():
    assert se.derive_reset_signal(_reset(_ev("Leadership Change", "Yes"))) is True
    assert se.derive_reset_signal(_reset(_ev("Strategic Pivot", "yes"))) is False


def test_reset_unrecognized_type_does_not_fire_and_flags_review():
    # Flag 4: an unrecognized type does NOT auto-fire and is surfaced for review.
    ev = _reset(_ev("rebranding", "yes"))
    assert se.derive_reset_signal(ev) is False
    assert se.reset_needs_review(ev) is True


def test_reset_needs_review_false_for_recognized_or_empty():
    assert se.reset_needs_review(_reset(_ev("restructuring-layoffs", "yes"))) is False
    assert se.reset_needs_review(_reset()) is False


def test_reset_basis_for_firing_else_first_else_empty():
    zoe = _reset(_ev("strategic-pivot", "no", "pivot basis"),
                 _ev("restructuring-layoffs", "yes", "restructuring basis"))
    assert se.reset_basis_for(zoe) == "restructuring basis"   # the firing event's basis
    noom = _reset(_ev("strategic-pivot", "no", "pivot basis"))
    assert se.reset_basis_for(noom) == "pivot basis"          # nothing fires -> first-listed
    assert se.reset_basis_for(_reset()) == ""                  # empty -> empty


def test_reset_recalibration_from_stored_json():
    # Part C: derive off the persisted reset_events_json reproduces the bool (no re-research).
    zoe = _reset(_ev("strategic-pivot", "no", "p"), _ev("restructuring-layoffs", "yes", "r"))
    flat = se.flatten_reset_fields({"reset_evidence": zoe})
    row = {"reset_events_json": flat["reset_events_json"]}
    assert se.derive_reset_signal(row) is True
    assert se.reset_basis_for(row) == "r"


def test_flatten_reset_fields():
    parsed = {"reset_evidence": _reset(
        _ev("strategic-pivot", "no", "D2C->payer (src)"),
        _ev("restructuring-layoffs", "yes", "team rebuild toward expansion (src)"),
    )}
    flat = se.flatten_reset_fields(parsed)
    assert set(flat) == set(se.RESET_PERSIST_FIELDS)
    assert flat["reset_event_types"] == "strategic-pivot, restructuring-layoffs"
    roundtrip = json.loads(flat["reset_events_json"])
    assert [e["event_type"] for e in roundtrip] == ["strategic-pivot", "restructuring-layoffs"]


def test_flatten_reset_fields_missing_or_nondict():
    for parsed in ({}, {"reset_evidence": None}, {"reset_evidence": {"reset_events": "oops"}}, "not-a-dict"):
        flat = se.flatten_reset_fields(parsed)
        assert set(flat) == set(se.RESET_PERSIST_FIELDS)
        assert flat["reset_event_types"] == ""
        assert flat["reset_events_json"] == "[]"


# ---------------------------------------------------------------------------
# Slice 4 (Commit 2) — capability-fit averaging + missing-attribute (null) policy
# ---------------------------------------------------------------------------


def test_capability_average_rounds_and_clamps():
    assert se.derive_capability_fit_score(80, 70, 90) == (80, False)
    assert se.derive_capability_fit_score(74, 75, 76) == (75, False)
    assert se.derive_capability_fit_score(100, 100, 100) == (100, False)


def test_capability_null_suppresses_and_flags():
    # any None -> (None, True); must NOT average the two non-nulls (which would be 85)
    assert se.derive_capability_fit_score(80, None, 90) == (None, True)
    # string null sentinels behave the same as a real None
    assert se.derive_capability_fit_score("null", 70, 90) == (None, True)
    assert se.derive_capability_fit_score(80, 70, "") == (None, True)


def test_capability_zero_is_real_not_missing():
    # 0 is a genuine Absent finding -> averages normally, NOT suppressed/flagged
    assert se.derive_capability_fit_score(0, 0, 0) == (0, False)
    # and 0 pulls the average down rather than dropping out of it
    assert se.derive_capability_fit_score(0, 90, 90) == (60, False)


def test_capability_on_shape_high_off_shape_low():
    score_on, flag_on = se.derive_capability_fit_score(90, 88, 92)    # all strong
    assert flag_on is False and score_on >= 85
    score_off, flag_off = se.derive_capability_fit_score(40, 35, 30)  # B2B2C / periodic / bureaucratic
    assert flag_off is False and score_off <= 40


def test_flatten_capability_fields_six_columns_incl_null():
    parsed = {"capability_evidence": {
        "a1_score": 90, "a1_basis": "daily-use habit loop; subscription revenue",
        "a2_score": 0, "a2_basis": "no strain found; scaling smoothly",
        "a3_score": None, "a3_basis": "no consumer-habit evidence in the findings",
    }}
    out = se.flatten_capability_fields(parsed)
    for col in se.CAPABILITY_FIELDS:
        assert col in out
    assert out["capability_a3_score"] is None        # null carried (couldn't assess)
    assert out["capability_a3_basis"] == "no consumer-habit evidence in the findings"
    assert out["capability_a2_score"] == 0.0         # 0 is a real Absent, preserved (not None)
    assert out["capability_a1_score"] == 90.0
    # round-trip: re-deriving from the stored components reproduces the suppression
    assert se.derive_capability_fit_score(
        out["capability_a1_score"], out["capability_a2_score"], out["capability_a3_score"]
    ) == (None, True)


def test_flatten_capability_tolerates_missing_block():
    for parsed in ({}, {"capability_evidence": None}, "not-a-dict"):
        out = se.flatten_capability_fields(parsed)
        assert set(out) == set(se.CAPABILITY_FIELDS)
        assert out["capability_a1_score"] is None and out["capability_a1_basis"] == ""
