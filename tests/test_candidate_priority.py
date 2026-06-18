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
    infer_signals,
    scale_path_quality,
    signal_text_to_score,
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
