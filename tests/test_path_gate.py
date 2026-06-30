"""Commit 2 — deterministic tests for the §B3 PATH-to-scale gate.

Built against SOT §B2/§B3 (FRAMEWORK_VERSION v1.13), logic-faithful to the spike path_gate.
Fully deterministic (runs on the Commit-1 classifier label + evidence presence checks) — no LLM,
no Colab split. The gate is a LOOSE engine-alive floor; engine STRENGTH is PMF's job (B1).
"""

import pytest

from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# Test A — the B2B floor: business_model == "B2B" -> GATE_FAIL (no consumer end-user).
# Runs on the Commit-1 label, so a locked-floor company (forced B2B) fails here via the override.
# ---------------------------------------------------------------------------

def test_test_a_floors_b2b_even_with_rich_evidence():
    # a B2B company with revenue + a payer channel still FAILS Test A — there is no consumer.
    row = {"revenue_or_arr": "$120M ARR (Sacra)", "payer_institutional_finding": "Aetna, covered lives"}
    passed, reason = se.path_gate("B2B", row)
    assert passed is False
    assert "Test A" in reason


@pytest.mark.parametrize("company", sorted(se.LOCKED_B2B_FLOOR))
def test_floor_companies_fail_path_via_their_b2b_label(company):
    # end-to-end: a floor company (forced B2B by Commit 1) -> Test A FAIL, regardless of evidence.
    label, _ = se.business_model_for(company, who_uses="consumer", who_pays="institution")  # adversarial read
    assert label == "B2B"
    passed, _ = se.path_gate(label, {"revenue_or_arr": "$80M", "payer_institutional_finding": "Medicaid"})
    assert passed is False


# ---------------------------------------------------------------------------
# Test B — B2C engine-alive (revenue OR user-scale OR growth; no-revenue fallback ^c10)
# ---------------------------------------------------------------------------

def test_b2c_alive_on_revenue():
    passed, _ = se.path_gate("B2C", {"revenue_or_arr": "$1B run-rate estimated (Sacra, 2025)"})
    assert passed is True


def test_b2c_no_revenue_fallback_passes_on_user_scale():
    """The ^c10 no-revenue fallback: a B2C company with NO revenue figure still PASSES on
    meaningful user-scale (missing revenue != dead)."""
    row = {"revenue_or_arr": "No company-reported ARR found",
           "sponsored_user_scale": "2M registered users",
           "growth_signal": ""}
    assert se.has_any_revenue(row) is False
    passed, reason = se.path_gate("B2C", row)
    assert passed is True
    assert "B2C" in reason


def test_b2c_no_revenue_fallback_passes_on_growth():
    row = {"revenue_or_arr": "", "sponsored_user_scale": "", "growth_signal": "growing ~120% YoY"}
    passed, _ = se.path_gate("B2C", row)
    assert passed is True


def test_b2c_declining_growth_is_not_a_positive_signal():
    row = {"revenue_or_arr": "", "sponsored_user_scale": "", "growth_signal": "revenue declining 20%"}
    assert se.has_positive_growth_signal(row) is False


def test_b2c_dead_fails():
    row = {"revenue_or_arr": "none found", "sponsored_user_scale": "none", "growth_signal": "none"}
    passed, reason = se.path_gate("B2C", row)
    assert passed is False
    assert "DEAD" in reason


# ---------------------------------------------------------------------------
# Test B — B2B2C real institutional channel (incl. the EMPLOYER-DIRECT scope fix)
# ---------------------------------------------------------------------------

def test_b2b2c_passes_on_named_payer():
    row = {"payer_institutional_finding": "In-network with Aetna and BCBS in several states"}
    assert se.path_gate("B2B2C", row)[0] is True


def test_b2b2c_passes_on_covered_lives():
    row = {"payer_institutional_finding": "Contracts covering ~250,000 covered lives across plans"}
    assert se.path_gate("B2B2C", row)[0] is True


def test_b2b2c_employer_direct_scope_fix_function_health_gap():
    """The §B3 scope fix: an EMPLOYER-DIRECT channel (insurance-free) is a real institutional channel.
    Function Health's 'Function for Work' employer channel must PASS Test B — a payer-only check would
    wrongly fail it."""
    row = {"payer_institutional_finding": "Function for Work: an employer-sponsored benefit partner program",
           "business_model_type": "primarily consumer cash-pay, no insurance"}
    assert se.has_real_institutional_channel(row) is True
    assert se.path_gate("B2B2C", row)[0] is True


def test_b2b2c_fails_on_positioning_only():
    row = {"payer_institutional_finding": "exploring future payer partnerships; in early conversations",
           "business_model_type": "D2C membership"}
    passed, reason = se.path_gate("B2B2C", row)
    assert passed is False
    assert "no real institutional channel" in reason


# ---------------------------------------------------------------------------
# Unmapped / empty business_model -> FAIL (never a silent pass)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bm", ["", "UNKNOWN", None])
def test_unmapped_business_model_fails(bm):
    passed, reason = se.path_gate(bm, {"revenue_or_arr": "$50M"})
    assert passed is False
    assert "unmapped" in reason


# ---------------------------------------------------------------------------
# Robust $-figure detection (presence ANYWHERE, not a prefix check)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("No company-reported ARR, but Sacra estimates $100M", True),  # hedge-led: must still detect
        ("$298M Series B; ~$50M ARR", True),                           # revenue magnitude
        ("~1.3M rings sold", True),                                    # plain magnitude (no $)
        ("$5.99/month membership", False),  # a unit PRICE is NOT a revenue magnitude (faithful to spike _figure)
        ("no revenue disclosed", False),
        ("", False),
    ],
)
def test_money_figure_detection(text, expected):
    assert se._has_money_figure(text) is expected
