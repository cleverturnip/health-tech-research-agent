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
    capability_fit_score,
    infer_signals,
    operator_agency_entry_score,
    reset_signal,
    scale_path_quality,
    signal_text_to_score,
    target_archetype,
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
# §9 — reset signal (text-scan, no hardcoded company names)
# ---------------------------------------------------------------------------

def test_reset_signal_text_scan():
    assert reset_signal({"review_notes": "leadership churn and a pivot"}) is True
    assert reset_signal({"final_takeaway": "steady growth, strong retention"}) is False


def test_reset_signal_has_no_hardcoded_company_names():
    # A company name alone (e.g. ZOE) must never trigger reset — only researched text does.
    assert reset_signal({"company": "ZOE", "final_takeaway": "steady growth"}) is False


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
        "final_takeaway": "major restructure and turnaround underway",
    }
    assert operator_agency_entry_score(row) == 78


def test_agency_entry_clamped_and_int():
    score = operator_agency_entry_score({"operator_timing_score": 150})
    assert isinstance(score, int) and score == 100


# ---------------------------------------------------------------------------
# §4 — interim capability-fit bridge
# ---------------------------------------------------------------------------

def test_capability_fit_is_role_fit_bridge():
    assert capability_fit_score({"katelynd_role_fit_score": 81}) == 81


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
