"""Commit 8 — deterministic tests for the CHECKPOINT ADAPTER (raw research row -> score_company contract).

The `_FINAL` regen checkpoint is 11 columns (six findings + growth/paying/org findings + fit_brief_json +
company); the scoring inputs live INSIDE fit_brief_json. These tests use a synthetic fit_brief_json that
MIRRORS the real season-health structure (commercial_evidence with the OLD `user_scale_signal` key,
maturity_evidence.funding_rounds, capability_evidence.a2_score, reset_evidence). No LLM.
"""

import json

from health_tech_research_agent import structured_evidence as se


def _fit_brief():
    return {
        "commercial_evidence": {
            "revenue_or_arr": "$12.3M ARR (Latka)", "paying_customer_count": "",
            "user_scale_signal": "200k members",                 # OLD key (pre-v1.3 rename)
            "revenue_per_user": "", "growth_signal": "growing ~50% YoY",
            "business_model_type": "payer-reimbursed", "funding_evidence": "",
        },
        "maturity_evidence": {
            "funding_rounds": [{"type": "series-b", "series_designation": "series-b",
                                "date": "2023-01-15", "is_priced_equity": True}],
            "ipo_event": {}, "ipo_status": "private",
        },
        "capability_evidence": {"a1_score": 60, "a1_basis": "", "a2_score": 72, "a2_basis": "",
                                "a3_score": 50, "a3_basis": ""},
        "reset_evidence": {"reset_events": []},
    }


def _row(**kw):
    base = {
        "company": "season health",
        "fit_brief_json": json.dumps(_fit_brief()),
        "operating_characteristics_finding": "daily nutrition program the member follows",
        "commercial_scale_finding": "partners with health plans; covered lives",
        "outcomes_finding": "clinical outcomes reported",
        "payer_institutional_finding": "in-network coverage in some states",
        "growth_finding": "ARR grew year over year",
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# evidence assemblies (folded in from the signed cells — tested, not cell-side)
# ---------------------------------------------------------------------------

def test_background_fit_evidence_is_the_three_signed_fields():
    ev = se.background_fit_evidence(_row())
    assert "daily nutrition program" in ev          # operating_characteristics_finding
    assert "partners with health plans" in ev       # commercial_scale_finding
    assert "clinical outcomes" in ev                 # outcomes_finding
    # joined with the blank-filter (empty fields dropped)
    assert se.background_fit_evidence({"operating_characteristics_finding": "only this"}) == "only this"


def test_classifier_evidence_is_the_three_signed_fields():
    ev = se.classifier_evidence(_row())
    assert "partners with health plans" in ev        # commercial_scale_finding
    assert "in-network coverage" in ev               # payer_institutional_finding
    assert "daily nutrition program" in ev           # operating_characteristics_finding


def test_evidence_char_cap():
    big = {"operating_characteristics_finding": "x" * 20000}
    assert len(se.background_fit_evidence(big)) == se._EVIDENCE_CHAR_CAP


# ---------------------------------------------------------------------------
# flatten_checkpoint_row — the fit_brief_json bridge
# ---------------------------------------------------------------------------

def test_flatten_unpacks_commercial_and_maturity():
    flat = se.flatten_checkpoint_row(_row())
    assert flat["revenue_or_arr"] == "$12.3M ARR (Latka)"
    assert "growing" in flat["growth_signal"]
    assert flat["business_model_type"] == "payer-reimbursed"
    assert flat["funding_stage"] == "series-b"        # derived from funding_rounds


def test_flatten_maps_old_user_scale_signal_key():
    # the checkpoint carries user_scale_signal (old); the adapter maps it to sponsored_user_scale
    flat = se.flatten_checkpoint_row(_row())
    assert flat["sponsored_user_scale"] == "200k members"


def test_flatten_produces_capability_and_reset_columns():
    flat = se.flatten_checkpoint_row(_row())
    assert se._score_or_none(flat["capability_a2_score"]) == 72
    assert flat["reset_events_json"] == "[]"


def test_flatten_carries_raw_findings_top_level():
    flat = se.flatten_checkpoint_row(_row())
    assert flat["operating_characteristics_finding"].startswith("daily nutrition")


def test_flatten_tolerates_blank_or_malformed_fit_brief():
    for bad in ("", "{not json", "[]"):
        flat = se.flatten_checkpoint_row(_row(fit_brief_json=bad))
        assert flat["funding_stage"] in ("unknown", "")   # no crash; no silent bogus stage


def test_funding_patch_rederives_equip_to_series_c():
    # the DOCUMENTED_FUNDING_PATCHES data refresh appends equip's real Series C (2024) + undesignated $54M
    # (2025) -> stage re-derives series-c (the $54M does NOT advance to series-d). A DATA refresh, re-derived.
    fb = _fit_brief()
    fb["maturity_evidence"] = {
        "funding_rounds": [{"series_designation": "series-a", "date": "2021-02", "is_priced_equity": True},
                           {"series_designation": "series-b", "date": "2021-05", "is_priced_equity": True}],
        "ipo_event": {}, "ipo_status": "private"}
    flat = se.flatten_checkpoint_row(_row(company="equip health", fit_brief_json=json.dumps(fb)))
    assert flat["funding_stage"] == "series-c"
    assert se.flatten_checkpoint_row(_row(company="acme"))["funding_stage"] == "series-b"  # non-patched unaffected


# ---------------------------------------------------------------------------
# strain faithful-fix — score_company reads operating_characteristics_finding (was a dead column)
# ---------------------------------------------------------------------------

def test_strain_reads_operating_characteristics_finding():
    # a2=50 (below the 55 MODERATE bar) -> strain must come from the speed-of-scale TEXT in the finding.
    # pre-fix this read the non-existent `operating_characteristics` column and silently scored 0.
    fb = _fit_brief()
    fb["capability_evidence"]["a2_score"] = 50
    row = _row(fit_brief_json=json.dumps(fb),
               operating_characteristics_finding="scaled from 100 -> 500 staff in ~6 months")
    out = se.score_checkpoint_row(row, classifier_read={"who_uses": "consumer", "who_pays": "consumer"},
                                  background_fit=7)
    assert out["strain"] == 1        # speed-of-scale fired from the finding text


# ---------------------------------------------------------------------------
# score_checkpoint_row — end-to-end from a raw row + the three live reads
# ---------------------------------------------------------------------------

def test_score_checkpoint_row_end_to_end():
    out = se.score_checkpoint_row(
        _row(),
        classifier_read={"who_uses": "consumer", "who_pays": "mixed", "who_uses_confidence": "high"},
        growth_read={"growth_kind": "rate", "growth_rate_pct": "50", "growth_magnitude_usd_m": "",
                     "growth_qualitative": "", "growth_source": "estimate"},
        background_fit=7,
    )
    assert out["business_model"] == "B2B2C"          # consumer + mixed -> B2B2C
    assert out["funding_stage"] == "series-b"
    assert out["model_priority"] in se.PRIORITY_TIERS
    assert out["final_priority"] in se.PRIORITY_TIERS


def test_documented_reset_override_forces_no_fire():
    # hinge/noom: the emitter mis-fires (public-layoff / growth-support exec-add); the human override forces
    # no-fire regardless of the emitted events, authoritative over the emitter.
    firing = '[{"event_type": "restructuring-layoffs", "creates_high_agency_opening": "yes"}]'
    assert se.reset_signal_for_row({"company": "hinge health", "reset_events_json": firing}) is False
    assert se.reset_signal_for_row({"company": "noom med", "reset_events_json": firing}) is False
    # a non-overridden company with the SAME firing event still fires
    assert se.reset_signal_for_row({"company": "other co", "reset_events_json": firing}) is True


def test_reset_signal_for_row_raises_on_unflattened_row():
    # the raw checkpoint row has no reset_events_json -> reading reset on it is a WIRING BUG -> raise LOUD
    # (this is the class of bug that floored grow invisibly)
    import pytest
    with pytest.raises(KeyError):
        se.reset_signal_for_row({"company": "x"})   # no reset_events_json
    # a flattened row is fine
    flat = se.flatten_checkpoint_row(_row())
    assert se.reset_signal_for_row(flat) in (True, False)


def test_score_checkpoint_row_absent_growth_is_not_a_crash():
    # no growth_read -> genuine-absent (pmf cap), never a guessed rate
    out = se.score_checkpoint_row(_row(), classifier_read={"who_uses": "consumer", "who_pays": "consumer"},
                                  background_fit=6)
    assert out["model_priority"] in se.PRIORITY_TIERS
