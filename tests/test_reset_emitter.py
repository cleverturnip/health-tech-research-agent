"""Commit 3a — the substance-classifying reset emitter (build_fit_brief_prompt reset block, SOT v1.15).

The emitter wording is LLM-facing (co-drafted + signed off); its LIVE validation over the 5 regression
companies is a Colab run (it produces the reset_events). What is testable OFFLINE here:

1. PROMPT FIDELITY — the signed wording landed in the production prompt (substance-over-framing; ipo-prep
   type; the tightened declared-transformation/strategic-pivot split; growth-support -> "unclear").
2. THE EMITTER -> derive_reset_signal CONTRACT — the load-bearing proof of WHY the emitter change matters:
   the deterministic rule (already correct, no basis-regex) gives the WRONG answer on the OLD emitter's
   real output for sword/oura/noom (they fire), and the RIGHT answer on the substance-classified output the
   v1.15 emitter is signed to produce. So the OUTCOME is determined entirely by the emitter's classification
   — which the live Colab run validates.
"""

import pytest

from health_tech_research_agent import research_runner as rr
from health_tech_research_agent import structured_evidence as se


# ---------------------------------------------------------------------------
# 1. Prompt fidelity — the signed wording is in the production fit-brief prompt.
# ---------------------------------------------------------------------------

def _prompt():
    return rr.build_fit_brief_prompt("ACME Health", "findings...", "taxonomy block")


def test_emitter_classifies_by_substance_not_framing():
    p = _prompt()
    assert "CLASSIFY BY SUBSTANCE, NOT PRESS FRAMING" in p
    # the old transcribe-don't-re-derive instruction is gone (it let sword/oura through)
    assert "do NOT re-derive or override the opening here" not in p


def test_emitter_has_ipo_prep_type():
    p = _prompt()
    assert "ipo-prep — IPO preparation" in p
    assert "ipo-prep" in p.split("reset_events")[-1]  # also in the emitted-JSON schema enum


def test_emitter_tightened_transformation_vs_pivot():
    p = _prompt()
    assert "OPERATING-MODEL rebuild" in p                       # declared-transformation = internal rebuild only
    assert '"evolution" into a different kind of product' in p   # such "evolution" = strategic-pivot


def test_emitter_exec_add_structural_role_rule():
    # v1.16: exec-add opening read by STRUCTURAL ROLE (build a missing function -> yes; staff growth -> unclear)
    p = _prompt()
    assert "EXEC ADD — read the opening by STRUCTURAL ROLE" in p
    assert "FIRST-EVER / NEWLY-CREATED C-suite seat" in p
    assert 'BUILD a missing operating function (-> "yes") or STAFF an existing growth thrust' in p


# ---------------------------------------------------------------------------
# 2. The emitter -> derive_reset_signal contract (the load-bearing proof).
# OLD = the real pre-3a emitted reset_events (from the regen CSV). NEW = the substance-classified
# events the v1.15 emitter is signed to produce. Same deterministic rule; the emitter decides the outcome.
# ---------------------------------------------------------------------------

def _t(event_type, opening):
    return {"event_type": event_type, "creates_high_agency_opening": opening}


# The REAL pre-3a emitter output (extracted from the regen checkpoint) — 3 of these mis-fire.
OLD_EMITTER = {
    "foodsmart": [_t("founder-transition", "yes"), _t("leadership-change", "yes")],
    "grow therapy": [_t("leadership-change", "yes"), _t("declared-transformation", "yes"), _t("strategic-pivot", "unclear")],
    "sword health": [_t("leadership-change", "unclear"), _t("strategic-pivot", "yes"),
                     _t("declared-transformation", "yes"), _t("declared-transformation", "unclear")],
    "oura": [_t("declared-transformation", "yes"), _t("strategic-pivot", "yes"), _t("ma-integration", "yes")],
    "noom med": [_t("strategic-pivot", "yes"), _t("leadership-change", "yes"), _t("founder-transition", "unclear")],
}

# What the v1.15 substance-classifying emitter is SIGNED to produce (the 3 re-classifications):
#   sword "Intelligence evolution": declared-transformation/yes -> strategic-pivot/no
#   oura  S-1:                      declared-transformation/yes -> ipo-prep/no
#   noom  CMO "to support expansion": leadership-change/yes     -> leadership-change/unclear
NEW_EMITTER = {
    "foodsmart": [_t("founder-transition", "yes"), _t("leadership-change", "yes")],
    "grow therapy": [_t("leadership-change", "yes"), _t("strategic-pivot", "no")],
    "sword health": [_t("leadership-change", "unclear"), _t("strategic-pivot", "no"),
                     _t("strategic-pivot", "no"), _t("strategic-pivot", "unclear")],
    "oura": [_t("ipo-prep", "no"), _t("strategic-pivot", "no"), _t("ma-integration", "no")],
    "noom med": [_t("strategic-pivot", "no"), _t("leadership-change", "unclear"), _t("founder-transition", "unclear")],
}

EXPECTED = {"foodsmart": True, "grow therapy": True,
            "sword health": False, "oura": False, "noom med": False}


@pytest.mark.parametrize("company", list(EXPECTED))
def test_new_emitter_output_lands_the_5_regressions(company):
    fired = se.derive_reset_signal({"reset_events": NEW_EMITTER[company]})
    assert fired is EXPECTED[company], f"{company}: v1.15 emitter output should -> fire={EXPECTED[company]}"


@pytest.mark.parametrize("company", ["sword health", "oura", "noom med"])
def test_old_emitter_output_mis_fires_proving_the_emitter_is_the_fix(company):
    # the deterministic rule is already correct; the OLD emitter's MISLABELS are what made these fire.
    # this is why 3a moves the judgment into the emitter (substance classification), not a basis-regex.
    assert se.derive_reset_signal({"reset_events": OLD_EMITTER[company]}) is True  # WRONG outcome, OLD labels


def test_no_basis_regex_in_package():
    # the spike's basis-regex bridge (_PIVOT_SUBSTANCE / _IPO_PREP / _GROWTH_SUPPORT) is NOT ported.
    import inspect
    src = inspect.getsource(se)
    for needle in ("_PIVOT_SUBSTANCE", "_IPO_PREP", "_GROWTH_SUPPORT"):
        assert needle not in src


def test_reset_decision_is_type_plus_opening_only():
    # a firing type needs opening=="yes"; a never-fire type never fires even at opening=="yes".
    assert se.derive_reset_signal({"reset_events": [_t("leadership-change", "yes")]}) is True
    assert se.derive_reset_signal({"reset_events": [_t("ipo-prep", "yes")]}) is False
    assert se.derive_reset_signal({"reset_events": [_t("strategic-pivot", "yes")]}) is False
    assert se.derive_reset_signal({"reset_events": [_t("leadership-change", "unclear")]}) is False
