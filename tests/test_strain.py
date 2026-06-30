"""Commit 6 — deterministic tests for the §B7 STRAIN modifier (0..+2, max LOCKED +2).

Logic-faithful to the spike strain: structured a2_score (>=70 -> 2; >=55 -> 1) + a speed-of-scale text
signal -> 1; default LOW (0) otherwise (absence-is-a-finding). Strength-tagged. Fully deterministic.
"""

import pytest

from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# a2 bands
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a2, expected_score, expected_strength", [
    (100, 2, "STRONG"),
    (70, 2, "STRONG"),
    (69, 1, "MODERATE"),   # >=55 -> MODERATE
    (55, 1, "MODERATE"),
    (54, 0, "WEAK"),
    (0, 0, "WEAK"),        # 0 is a real "Absent" capability value, not missing -> WEAK
])
def test_strain_a2_bands(a2, expected_score, expected_strength):
    score, strength, _ = se.strain_score(a2, "")
    assert (score, strength) == (expected_score, expected_strength)


def test_strain_max_is_locked_at_2():
    # a high a2 cannot exceed +2.
    assert se.strain_score(100, "headcount 100 -> 500 in ~6mo doubled")[0] == 2


# ---------------------------------------------------------------------------
# speed-of-scale text signal (B1-structural)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "headcount 100 -> 500 in 6 months",
    "scaled from 100 to 500 staff",
    "grew the team in ~6 months",
    "doubled its headcount last year",
])
def test_speed_of_scale_gives_moderate(text):
    score, strength, basis = se.strain_score(None, text)
    assert (score, strength) == (1, "MODERATE")
    assert basis == "speed-of-scale"


def test_no_speed_signal_is_weak():
    score, strength, basis = se.strain_score(None, "a stable team of 50 employees, steady operations")
    assert (score, strength, basis) == (0, "WEAK", "default-low")


# ---------------------------------------------------------------------------
# precedence + absence
# ---------------------------------------------------------------------------

def test_a2_strong_takes_precedence_over_speed():
    score, strength, basis = se.strain_score(80, "headcount 100 -> 500")
    assert (score, strength) == (2, "STRONG")
    assert basis == "a2=80"


def test_a2_none_no_speed_is_default_low():
    assert se.strain_score(None, "") == (0, "WEAK", "default-low")
    assert se.strain_score("n/a", "") == (0, "WEAK", "default-low")


def test_a2_moderate_basis_cites_a2():
    assert se.strain_score(60, "")[2] == "a2=60"
