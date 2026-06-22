"""Tests for the candidate-priority engine, Commit 1: signal conversion (§1)
and the reconciled scale-path classifier (§2).

The load-bearing test is `test_producer_outputs_are_all_gate_recognized` — the
vocabulary closure test. cell159 emitted `strong_single_engine` /
`credible_single_engine` / `outcomes_plus_path`, names the V4.1 gate's accepted
lists do not contain; such a value silently reads as "no scale path" and demotes
a strong company. This test fails for any producer output the gate would not
recognize, so a vocabulary regression can never ship silently.
"""

from itertools import product

import pytest

from health_tech_research_agent import candidate_priority as cp
from health_tech_research_agent.structured_evidence import derive_capability_fit_score
from health_tech_research_agent.candidate_priority import (
    CREDIBLE_DUAL_PATH,
    CREDIBLE_PATH,
    EMERGING_PATH,
    PRODUCER_SCALE_PATHS,
    RECOGNIZED_SCALE_PATHS,
    STRONG_COMMERCIAL_ENGINE,
    STRONG_DUAL_ENGINE,
    STRONG_INSTITUTIONAL_ENGINE,
    WEAK_OR_UNCLEAR,
    apply_public_near_ipo_cap,
    capability_fit_score,
    compute_candidate_priority,
    infer_signals,
    operator_agency_entry_score,
    reset_signal,
    scale_path_quality,
    signal_text_to_score,
    target_archetype,
    v41_gate,
)


# ---------------------------------------------------------------------------
# §1 — signal conversion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("strong", 3), ("Strong", 3), ("  STRONG ", 3),
        ("moderate", 2), ("weak", 1),
        ("none", 0), ("", 0), (None, 0), ("anything-else", 0),
    ],
)
def test_signal_text_to_score(text, expected):
    assert signal_text_to_score(text) == expected


def test_infer_signals_reads_text_columns():
    row = {
        "commercial_scale_signal": "strong",
        "institutional_distribution_signal": "moderate",
        "outcomes_signal": "weak",
    }
    assert infer_signals(row) == {
        "commercial_scale_signal_inferred": 3,
        "institutional_distribution_signal_inferred": 2,
        "outcomes_signal_inferred": 1,
    }


# ---------------------------------------------------------------------------
# §2 — reconciled scale-path: one case per branch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "commercial, institutional, outcomes, pmf, evidence, plausible, expected",
    [
        # both strong -> dual
        (3, 3, 0, 0, 0, False, STRONG_DUAL_ENGINE),
        # institutional-only strong, qualifies via outcomes>=2 -> institutional engine
        (0, 3, 2, 0, 0, False, STRONG_INSTITUTIONAL_ENGINE),
        # institutional-only strong, qualifies via pmf>=78 -> institutional engine
        (1, 3, 0, 78, 0, False, STRONG_INSTITUTIONAL_ENGINE),
        # institutional-only strong, fails both -> credible_path (was credible_single_engine)
        (0, 3, 0, 50, 0, False, CREDIBLE_PATH),
        # commercial-only strong, qualifies -> commercial engine
        (3, 0, 2, 0, 0, False, STRONG_COMMERCIAL_ENGINE),
        # commercial-only strong, fails both -> credible_path
        (3, 1, 0, 50, 0, False, CREDIBLE_PATH),
        # plausible path
        (1, 1, 0, 70, 60, True, CREDIBLE_PATH),
        # outcomes-led (was outcomes_plus_path) -> emerging
        (2, 0, 3, 0, 0, False, EMERGING_PATH),
        # some signal >= 2 -> emerging
        (0, 2, 0, 0, 0, False, EMERGING_PATH),
        # nothing -> weak_or_unclear
        (1, 1, 1, 0, 0, False, WEAK_OR_UNCLEAR),
        (0, 0, 0, 0, 0, False, WEAK_OR_UNCLEAR),
    ],
)
def test_scale_path_branches(commercial, institutional, outcomes, pmf, evidence, plausible, expected):
    assert scale_path_quality(commercial, institutional, outcomes, pmf, evidence, plausible) == expected


def test_scale_path_nan_pmf_treated_as_failing_threshold():
    # institutional-only strong, outcomes<2, pmf is NaN -> must not qualify as strong
    assert scale_path_quality(0, 3, 0, float("nan"), 0, False) == CREDIBLE_PATH


# ---------------------------------------------------------------------------
# THE LINCHPIN — vocabulary closure (producer outputs ⊆ gate-recognized names)
# ---------------------------------------------------------------------------

def _all_producer_outputs():
    """Every scale_path_quality output across the full signal space."""
    outputs = set()
    for commercial, institutional, outcomes in product(range(4), repeat=3):
        for pmf in (0, 50, 68, 78, 90):
            for evidence in (0, 50, 60):
                for plausible in (True, False):
                    outputs.add(
                        scale_path_quality(commercial, institutional, outcomes, pmf, evidence, plausible)
                    )
    return outputs


def test_producer_outputs_are_all_gate_recognized():
    # Exhaustive: nothing the producer can emit is unknown to the gate.
    observed = _all_producer_outputs()
    unrecognized = observed - RECOGNIZED_SCALE_PATHS
    assert not unrecognized, f"producer emits gate-unrecognized scale paths: {sorted(unrecognized)}"


def test_declared_producer_vocabulary_matches_reality():
    # The declared emittable set equals what the function actually emits...
    assert _all_producer_outputs() == set(PRODUCER_SCALE_PATHS)
    # ...and the declared set is a subset of what the gate recognizes.
    assert PRODUCER_SCALE_PATHS <= RECOGNIZED_SCALE_PATHS


def test_credible_dual_path_accepted_by_gate_but_never_emitted():
    # spec 2c: the gate accepts it, the producer must never emit it.
    assert CREDIBLE_DUAL_PATH in cp.HAS_STRONG_SCALE_PATH
    assert CREDIBLE_DUAL_PATH not in _all_producer_outputs()


# ---------------------------------------------------------------------------
# §9 — reset signal (reads the researched field; text-scan retired)
# ---------------------------------------------------------------------------

def test_reset_signal_reads_stored_field_zoe_type():
    # A stored/researched reset determination (incl. a manual override) is detected,
    # even with no reset terms anywhere in the text fields.
    assert reset_signal({
        "reset_or_restructure_signal": "1.0",
        "reset_or_restructure_basis": "manual_reset_override_for_audit",
        "final_takeaway": "steady growth, strong retention",
    }) is True
    assert reset_signal({"reset_or_restructure_signal": "yes"}) is True


def test_reset_signal_ignores_incidental_text_videahealth_type():
    # Incidental 'integration'/'pivot'/'rebuild' language with NO stored reset signal
    # must NOT flag reset (the old text-scan false-positive, e.g. "workflow integration").
    assert reset_signal({
        "reset_or_restructure_signal": "0.0",
        "review_notes": "enterprise adoption, Series B timing, workflow integration",
    }) is False
    assert reset_signal({"final_takeaway": "a clean pivot to platform integration and rebuild"}) is False


def test_reset_signal_blank_or_unclear_is_false():
    assert reset_signal({}) is False                                    # older-round companies: no field
    assert reset_signal({"reset_or_restructure_signal": ""}) is False
    assert reset_signal({"reset_or_restructure_signal": "unclear"}) is False
    assert reset_signal({"reset_or_restructure_signal": "0"}) is False


# ---------------------------------------------------------------------------
# §3 — agency-entry: band precedence (max/min stacking is authoritative)
# ---------------------------------------------------------------------------

def test_agency_entry_band_precedence_stacks_via_max():
    # early-growth(86) + ideal(85) + high-agency(80): the highest floor must win.
    row = {
        "operator_timing_score": 70,
        "katelynd_role_fit_score": 82,
        "pmf_scale_score": 74,
        "evidence_confidence_score": 60,
        "company_maturity_read": "early-growth",
        "stage_timing_fit": "ideal",
        "likely_agency_level": "high",
    }
    assert operator_agency_entry_score(row) == 86


def test_agency_entry_public_ceiling_without_high_agency():
    row = {
        "operator_timing_score": 90,
        "company_maturity_read": "public",
        "stage_timing_fit": "good",
    }
    assert operator_agency_entry_score(row) == 58


def test_agency_entry_reset_lifts_mature_scaleup():
    row = {
        "operator_timing_score": 50,
        "company_maturity_read": "scale-up",
        "stage_timing_fit": "good",
        "reset_or_restructure_signal": "1.0",
    }
    assert operator_agency_entry_score(row) == 78


def test_agency_entry_clamped_and_int():
    score = operator_agency_entry_score({"operator_timing_score": 150})
    assert isinstance(score, int) and score == 100


# ---------------------------------------------------------------------------
# §4 — real capability-fit (Slice 4 repoint; replaces the role_fit bridge)
# ---------------------------------------------------------------------------

def test_capability_fit_score_uses_real_not_bridge():
    # Repointed: reads katelynd_capability_fit_score, NOT the old katelynd_role_fit_score bridge.
    assert capability_fit_score(
        {"katelynd_capability_fit_score": 60, "katelynd_role_fit_score": 90}
    ) == 60


def test_capability_fit_score_none_when_absent_or_suppressed():
    # Absent (un-scored / pre-Slice-4 row) or a suppressed/blank score -> None (routes to review).
    assert capability_fit_score({"katelynd_role_fit_score": 90}) is None
    assert capability_fit_score({"katelynd_capability_fit_score": ""}) is None
    assert capability_fit_score({"katelynd_capability_fit_score": None}) is None


# ---------------------------------------------------------------------------
# §5 — archetype, incl. the reconciled-vocab eligibility (item 5a, same bug-class as §2)
# ---------------------------------------------------------------------------

def _ideal_row():
    return {
        "pmf_scale_score": 75,
        "evidence_confidence_score": 60,
        "company_maturity_read": "early-growth",
        "stage_timing_fit": "ideal",
    }


def test_archetype_institutional_strong_qualifies_ideal():
    # The reconciled producer emits strong_institutional_engine; the archetype
    # eligibility list must recognize it. Under the OLD list (strong_single_engine)
    # this same company silently fails to "Role-scope-dependent" — the §2 bug class.
    result = target_archetype(_ideal_row(), capability_fit=80, agency_entry=85,
                              scale_path=STRONG_INSTITUTIONAL_ENGINE)
    assert result == "Ideal early-growth / high-agency target"


def test_archetype_emerging_path_is_not_ideal():
    # §5a: emerging_path is excluded from the Ideal pool (gate caps it at P1), so an
    # otherwise-Ideal early-growth company on emerging_path is Role-scope-dependent.
    result = target_archetype(_ideal_row(), capability_fit=80, agency_entry=85,
                              scale_path=EMERGING_PATH)
    assert result == "Role-scope-dependent target"


def test_archetype_mature_benchmark():
    row = {"pmf_scale_score": 85, "evidence_confidence_score": 65,
           "company_maturity_read": "late-stage", "stage_timing_fit": "borderline"}
    assert target_archetype(row, 70, 60, EMERGING_PATH) == "Strong but mature benchmark"


def test_archetype_role_scope_dependent():
    row = {"pmf_scale_score": 66, "evidence_confidence_score": 55,
           "company_maturity_read": "early-growth", "stage_timing_fit": "good"}
    assert target_archetype(row, 75, 70, CREDIBLE_PATH) == "Role-scope-dependent target"


def test_archetype_under_proven():
    row = {"pmf_scale_score": 50, "evidence_confidence_score": 40,
           "company_maturity_read": "early-growth", "stage_timing_fit": "good"}
    assert target_archetype(row, 80, 85, CREDIBLE_PATH) == "Interesting but under-proven"


# ---------------------------------------------------------------------------
# §6 — V4.1 gate decision matrix
# ---------------------------------------------------------------------------

def _p0_inputs(**over):
    """A fully P0-qualifying input set; override fields to reach other tiers."""
    base = dict(
        maturity="early-growth", stage_fit="ideal", agency_level="high",
        thesis=85, pmf=80, evidence=65, capability=85, agency=85,
        scale_path=STRONG_INSTITUTIONAL_ENGINE, commercial=0, institutional=3, outcomes=2,
        archetype="Ideal early-growth / high-agency target", has_reset=False,
    )
    base.update(over)
    return base


def test_gate_p0():
    assert v41_gate(**_p0_inputs()) == "P0"


def test_gate_evidence_boundary_is_the_affect_case():
    # evidence 60 passes the P0 gate; 59 drops to P1 — exactly the Affect case.
    assert v41_gate(**_p0_inputs(evidence=60)) == "P0"
    assert v41_gate(**_p0_inputs(evidence=59)) == "P1"


def test_gate_p0_thresholds_each_drop_to_p1():
    # Each P0 score threshold, just below, drops to P1 (still clears P1 floors).
    assert v41_gate(**_p0_inputs(thesis=77)) == "P1"
    assert v41_gate(**_p0_inputs(pmf=73)) == "P1"
    assert v41_gate(**_p0_inputs(capability=77)) == "P1"
    assert v41_gate(**_p0_inputs(agency=81)) == "P1"


def test_gate_p1_standard():
    # institutional<3 fails P0's strong-channel requirement -> P1 standard.
    assert v41_gate(**_p0_inputs(scale_path=CREDIBLE_PATH, institutional=2, outcomes=1)) == "P1"


def test_gate_p1_special_early_growth_emerging():
    assert v41_gate(**_p0_inputs(
        scale_path=EMERGING_PATH, institutional=2, outcomes=2,
        archetype="Role-scope-dependent target",
    )) == "P1"


def test_gate_p1_special_scaleup_reset():
    assert v41_gate(**_p0_inputs(
        maturity="scale-up", stage_fit="good", has_reset=True,
        scale_path=CREDIBLE_PATH, institutional=1, outcomes=1,
        archetype="Role-scope-dependent target",
    )) == "P1"


def test_gate_mature_benchmark_in_gate_cap():
    # late-stage with otherwise-P1 scores -> mature cap removes P0/P1 -> P2.
    assert v41_gate(**_p0_inputs(
        maturity="late-stage", scale_path=CREDIBLE_PATH, institutional=2, outcomes=1,
        archetype="Strong but mature benchmark",
    )) == "P2"


def test_gate_scaleup_borderline_no_reset_capped():
    assert v41_gate(**_p0_inputs(
        maturity="scale-up", stage_fit="borderline", has_reset=False,
        scale_path=CREDIBLE_PATH, institutional=2, outcomes=1,
        archetype="Role-scope-dependent target",
    )) == "P2"


def test_gate_p2_floor():
    assert v41_gate(**_p0_inputs(
        maturity="scale-up", stage_fit="borderline",
        thesis=66, pmf=66, evidence=50, capability=66, agency=66,
        scale_path=CREDIBLE_PATH, institutional=1, outcomes=1,
        archetype="Role-scope-dependent target",
    )) == "P2"


def test_gate_p3_under_proven_and_weak_fit():
    assert v41_gate(**_p0_inputs(archetype="Interesting but under-proven")) == "P3"
    assert v41_gate(**_p0_inputs(archetype="Watch list / weak fit")) == "P3"


def test_gate_p3_fails_p2_floor():
    assert v41_gate(**_p0_inputs(
        maturity="scale-up", stage_fit="borderline", pmf=50, evidence=40,
        scale_path=WEAK_OR_UNCLEAR, institutional=0, outcomes=0,
        archetype="Role-scope-dependent target",
    )) == "P3"


# ---------------------------------------------------------------------------
# Slice 4 (Commit 3) — gate-time A1/A3 recompute for reset-lifted scale-ups.
# Double-count fix: A2-strain is already consumed by the reset cap-lift / agency floor, so a
# reset scale-up's P1 capability threshold uses the A1/A3 mean only — on BOTH P1 paths. Non-reset
# rows use the full capability. (The suppression GUARD + capability_needs_review FLAG ride with
# the repoint in Commit 4; here we prove the gate fix + that the gate is None-safe.)
# ---------------------------------------------------------------------------


def _reset_scaleup(**over):
    """A reset scale-up clearing the non-capability P1 floors; capability is the variable."""
    base = dict(
        maturity="scale-up", stage_fit="good", has_reset=True,
        scale_path=CREDIBLE_PATH, institutional=1, outcomes=1,
        archetype="Role-scope-dependent target",
        thesis=85, pmf=80, evidence=65, agency=85,
    )
    base.update(over)
    return _p0_inputs(**base)


def test_gate_reset_scaleup_compounding_blocked_on_a1a3_mean():
    # Full capability 76 (A2-inflated) WOULD clear P1, but the A1/A3 mean (70) does not -> P2.
    assert v41_gate(**_reset_scaleup(capability=76, capability_reset_adjusted=70)) == "P2"
    # control: with no adjusted value supplied, the full 76 clears P1 (fallback / pre-fix path).
    assert v41_gate(**_reset_scaleup(capability=76)) == "P1"


def test_gate_reset_scaleup_clears_on_a1a3_mean():
    # Mirror: clears P1 on the A1/A3 mean itself (79 >= 74), independent of A2.
    assert v41_gate(**_reset_scaleup(capability=76, capability_reset_adjusted=79)) == "P1"


def test_gate_reset_scaleup_p1_standard_path_also_uses_a1a3_mean():
    # scale-up/good + reset can also reach P1 via p1_standard (institutional>=2); the recompute
    # must cover it. Full 76 would clear p1_standard; the A1/A3 mean 70 blocks it -> P2.
    assert v41_gate(**_reset_scaleup(
        institutional=2, capability=76, capability_reset_adjusted=70,
    )) == "P2"


def test_gate_non_reset_uses_full_capability_no_a2_exclusion():
    # Non-reset row: the A1/A3 mean is NOT applied even if supplied; the full capability is used.
    # early-growth P1 (institutional<3), full capability 76 clears; adjusted 70 must be ignored.
    assert v41_gate(**_p0_inputs(
        scale_path=CREDIBLE_PATH, institutional=2, outcomes=1,
        capability=76, capability_reset_adjusted=70,   # has_reset=False default -> ignored
    )) == "P1"


def test_gate_reset_scaleup_none_capability_routes_to_p3_no_throw():
    # Adjusted-path null / suppression at the gate: A1 or A3 unscorable -> the full score is ALSO
    # suppressed, so capability AND capability_reset_adjusted both arrive None. The gate routes to
    # P3 (never P0/P1/P2) without throwing and without treating null as a 0 that could clear.
    # (The capability_needs_review FLAG + the end-to-end orchestrator routing ride with Commit 4.)
    assert v41_gate(**_reset_scaleup(capability=None, capability_reset_adjusted=None)) == "P3"


def test_compute_reset_scaleup_uses_a1a3_mean_post_repoint():
    # End-to-end (post-repoint): capability is the real stored score; the reset scale-up P1
    # threshold uses the A1/A3 mean derived from the components.
    base = {
        "company_maturity_read": "scale-up", "stage_timing_fit": "good", "likely_agency_level": "high",
        "thesis_fit_score": 85, "pmf_scale_score": 80, "evidence_confidence_score": 65,
        "katelynd_role_fit_score": 85, "operator_timing_score": 85,   # agency reads role_fit
        "commercial_scale_signal": "strong", "institutional_distribution_signal": "strong",
        "outcomes_signal": "strong", "plausible_near_term_scale_path": True,
        "reset_or_restructure_signal": "1.0",
    }
    # Low A1/A3 mean (70) blocks P1 even though the full score (78) and A2 (95) are high -> P2.
    low = {**base, "katelynd_capability_fit_score": 78,
           "capability_a1_score": 70, "capability_a2_score": 95, "capability_a3_score": 70}
    assert compute_candidate_priority(low)["candidate_priority_code"] == "P2"
    # High A1/A3 mean (80) clears P1 on the reset path -> P1.
    high = {**base, "katelynd_capability_fit_score": 85,
            "capability_a1_score": 80, "capability_a2_score": 95, "capability_a3_score": 80}
    assert compute_candidate_priority(high)["candidate_priority_code"] == "P1"


# ---------------------------------------------------------------------------
# §7 — public / near-IPO cap overlay (Q4)
# ---------------------------------------------------------------------------

def test_cap_public_without_reset_forced_p3():
    assert apply_public_near_ipo_cap("P2", "public", has_reset=False) == "P3"
    assert apply_public_near_ipo_cap("P1", "near-ipo", has_reset=False) == "P3"


def test_cap_public_with_reset_not_forced():
    assert apply_public_near_ipo_cap("P2", "public", has_reset=True) == "P2"


def test_cap_never_promotes():
    assert apply_public_near_ipo_cap("P3", "early-growth", has_reset=False) == "P3"


# ---------------------------------------------------------------------------
# Q4 end-to-end: public+reset -> P2 (never P0, never P3); public(no reset) -> P3
# ---------------------------------------------------------------------------

def _public_row(has_reset):
    row = {
        "company_maturity_read": "public", "stage_timing_fit": "good",
        "likely_agency_level": "high",
        "thesis_fit_score": 85, "pmf_scale_score": 82, "evidence_confidence_score": 65,
        "katelynd_role_fit_score": 80,  # feeds operator_agency_entry_score
        "katelynd_capability_fit_score": 80,  # real capability (Slice 4)
        "operator_timing_score": 80,
        "commercial_scale_signal": "strong", "institutional_distribution_signal": "strong",
        "outcomes_signal": "strong",
    }
    if has_reset:
        row["reset_or_restructure_signal"] = "1.0"
    return row


def test_q4_public_with_reset_is_p2():
    result = compute_candidate_priority(_public_row(has_reset=True))
    assert result["candidate_priority_code"] == "P2"


def test_q4_public_without_reset_is_p3():
    result = compute_candidate_priority(_public_row(has_reset=False))
    assert result["candidate_priority_code"] == "P3"


# ---------------------------------------------------------------------------
# Slice 4 (Commit 4) — engine repoint: suppression guard + end-to-end null routing
# ---------------------------------------------------------------------------

def test_compute_reset_scaleup_a1a3_null_is_p3_and_flagged():
    # Now reachable post-repoint: a reset scale-up with A2 present but A1 (or A3) unscorable ->
    # the full score is suppressed (derive -> None) -> P3 + capability_needs_review, never P0/P1/P2.
    score, needs_review = derive_capability_fit_score(None, 95, 70)  # A1 null
    assert score is None and needs_review is True
    row = {
        "company_maturity_read": "scale-up", "stage_timing_fit": "good", "likely_agency_level": "high",
        "thesis_fit_score": 85, "pmf_scale_score": 80, "evidence_confidence_score": 65,
        "katelynd_role_fit_score": 85, "operator_timing_score": 85,
        "commercial_scale_signal": "strong", "institutional_distribution_signal": "strong",
        "outcomes_signal": "strong", "plausible_near_term_scale_path": True,
        "reset_or_restructure_signal": "1.0",
        "katelynd_capability_fit_score": score,   # None (suppressed)
        "capability_a1_score": None, "capability_a2_score": 95, "capability_a3_score": 70,
    }
    result = compute_candidate_priority(row)
    assert result["candidate_priority_code"] == "P3"
    assert result["capability_needs_review"] is True


def test_compute_pre_slice4_row_suppresses_to_p3_flagged():
    # The transitional state: a component-less interim-master row has no capability score ->
    # capability None -> P3 + flag (cannot auto-tier on a missing capability read).
    row = {
        "company_maturity_read": "early-growth", "stage_timing_fit": "ideal", "likely_agency_level": "high",
        "thesis_fit_score": 85, "pmf_scale_score": 80, "evidence_confidence_score": 65,
        "katelynd_role_fit_score": 85, "operator_timing_score": 85,
        "commercial_scale_signal": "strong", "institutional_distribution_signal": "strong",
        "outcomes_signal": "strong",
    }
    out = compute_candidate_priority(row)
    assert out["candidate_priority_code"] == "P3"
    assert out["capability_needs_review"] is True


# ---------------------------------------------------------------------------
# Orchestrator outputs (§8) — P0-P3 only, interim framework stamp
# ---------------------------------------------------------------------------

def test_compute_candidate_priority_outputs():
    row = {
        "company_maturity_read": "early-growth", "stage_timing_fit": "ideal",
        "likely_agency_level": "high",
        "thesis_fit_score": 85, "pmf_scale_score": 80, "evidence_confidence_score": 65,
        "katelynd_role_fit_score": 85, "katelynd_capability_fit_score": 85,
        "operator_timing_score": 85,
        "commercial_scale_signal": "weak", "institutional_distribution_signal": "strong",
        "outcomes_signal": "moderate",
    }
    out = compute_candidate_priority(row, now_iso="2026-06-18T00:00:00Z")
    assert out["candidate_priority_code"] == "P0"
    assert out["candidate_priority_level"] == "P0: Active pursuit target"
    assert out["candidate_priority_rank"] == 0
    assert out["candidate_priority_framework_version"] == "V4.2"   # no longer interim (Slice 4)
    assert out["katelynd_capability_fit_score"] == 85
    assert out["capability_needs_review"] is False


def test_engine_never_emits_p4():
    # Q5: candidate engine ranks P0-P3 only.
    levels = set()
    for thesis in (90, 70, 40):
        for inst in (3, 1, 0):
            for mat in ("early-growth", "scale-up", "public", "late-stage"):
                out = compute_candidate_priority({
                    "company_maturity_read": mat, "stage_timing_fit": "ideal",
                    "likely_agency_level": "high", "thesis_fit_score": thesis,
                    "pmf_scale_score": thesis, "evidence_confidence_score": thesis,
                    "katelynd_role_fit_score": thesis,
                    "katelynd_capability_fit_score": thesis, "operator_timing_score": thesis,
                    "institutional_distribution_signal": {3: "strong", 1: "weak", 0: "none"}[inst],
                    "commercial_scale_signal": "none", "outcomes_signal": "moderate",
                })
                levels.add(out["candidate_priority_code"])
    assert levels <= {"P0", "P1", "P2", "P3"}


def test_reset_ripples_into_scaleup_borderline_p1_vs_p2():
    # scale-up + borderline: a STORED reset lifts it to P1 (scale-up+reset path);
    # without the stored signal it stays P2 — and incidental text must NOT lift it.
    base = dict(
        company_maturity_read="scale-up", stage_timing_fit="borderline", likely_agency_level="high",
        thesis_fit_score=80, pmf_scale_score=75, evidence_confidence_score=58,
        katelynd_role_fit_score=80, katelynd_capability_fit_score=80, operator_timing_score=80,
        commercial_scale_signal="strong", institutional_distribution_signal="strong", outcomes_signal="moderate",
    )
    with_reset = {**base, "reset_or_restructure_signal": "1.0"}
    without_reset = {**base, "reset_or_restructure_signal": "0.0",
                     "review_notes": "workflow integration and platform rebuild"}  # incidental, no stored signal
    assert compute_candidate_priority(with_reset)["candidate_priority_code"] == "P1"
    assert compute_candidate_priority(without_reset)["candidate_priority_code"] == "P2"


# ---------------------------------------------------------------------------
# §6 — P0 scale-path: strong commercial OR strong institutional qualifies (Commit B)
# ---------------------------------------------------------------------------

def test_p0_strong_commercial_qualifies():
    # Oura-like: strong commercial, weak institutional, early-growth, scores above P0 bars.
    # Previously blocked by the hard institutional>=3 condition; now reaches P0.
    assert v41_gate(**_p0_inputs(scale_path=STRONG_COMMERCIAL_ENGINE, commercial=3, institutional=0)) == "P0"


def test_p0_strong_institutional_still_qualifies():
    # No regression: a strong-institutional company still reaches P0.
    assert v41_gate(**_p0_inputs(scale_path=STRONG_INSTITUTIONAL_ENGINE, commercial=0, institutional=3)) == "P0"


def test_p0_strong_dual_still_qualifies():
    assert v41_gate(**_p0_inputs(scale_path=STRONG_DUAL_ENGINE, commercial=3, institutional=3)) == "P0"


def test_p0_strong_commercial_blocked_by_low_evidence():
    # Only the scale-path condition was relaxed: a strong-commercial co failing another
    # P0 bar (evidence < 60) is NOT P0 (it clears P1).
    result = v41_gate(**_p0_inputs(scale_path=STRONG_COMMERCIAL_ENGINE, commercial=3, institutional=0, evidence=59))
    assert result != "P0"
    assert result == "P1"


def test_p0_strict_commercial_bar_unchanged():
    # commercial < 3 (moderate) does not create a strong-commercial P0 path.
    result = v41_gate(**_p0_inputs(scale_path=EMERGING_PATH, commercial=2, institutional=1, outcomes=2))
    assert result != "P0"
