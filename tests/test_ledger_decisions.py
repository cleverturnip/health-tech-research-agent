"""Decision round-trip tests (Commit D) — render cards.csv, merge priority edits back with history,
never touching scores (Rule 8), human override winning (Rule 6)."""

from __future__ import annotations

import copy

import pytest

from health_tech_research_agent import ledger


DATE = "2026-07-02"
GATE = "gate2_batch03"


def _entry(company="function health", *, model_priority="P3", floor_ok=False, human_override="P1"):
    rec = dict(company=company, business_model="B2C", funding_stage="series-b",
               background_fit=4, pmf=10, arr_level=10, growth=10, strain=2, final_score=16,
               path_passed=True, agency_passed=True, gate_floored=False, floor_ok=floor_ok,
               model_priority=model_priority, human_override=human_override, floored_on_bg=False,
               tier_review=False, floor_reason="", data_feedback_loop="no",
               background_fit_basis="2x/yr", growth_note="high(+450%)", growth_evidence="+450%",
               strain_strength="MODERATE", strain_rationale="fast", path_detail="B2C alive",
               agency_detail="Series B in-window", reset_detail="none", revenue_or_arr="$298M ARR")
    return ledger.build_entry(rec, batch_id="b", date_scored=DATE, framework_version="v1.25")


def test_render_cards_csv_prefills_decision_columns():
    df = ledger.render_cards_csv([_entry()])
    assert list(df.columns) == ledger.CARDS_CONTEXT_COLUMNS + ledger.CARDS_DECISION_COLUMNS
    row = df.iloc[0]
    assert row["company"] == "function health" and row["model_priority"] == "P3"
    assert row["human_override"] == "" and row["override_reason"] == ""     # decision starts empty


def test_apply_override_sets_decision_history_and_wins():
    entries = [_entry()]
    decisions = [{"company": "function health", "human_override": "P1",
                  "override_reason": "revenue + complexity unicorn"}]
    out = ledger.apply_decisions(entries, decisions, decided_date=DATE, decided_at_gate=GATE)
    dec = out[0]["decision"]
    assert dec["human_override"] == "P1"
    assert dec["override_reason"] == "revenue + complexity unicorn"
    assert dec["decided_date"] == DATE and dec["decided_at_gate"] == GATE
    assert dec["history"] == [{"date": DATE, "field": "human_override", "from": None, "to": "P1",
                               "reason": "revenue + complexity unicorn"}]
    assert ledger.final_priority(out[0]) == "P1"                 # Rule 6 — override wins
    assert ledger.provenance(out[0]) == "human-overridden"


def test_scores_are_never_touched_by_a_decision():
    entries = [_entry()]
    before = copy.deepcopy(entries[0]["scoring"])
    out = ledger.apply_decisions(
        entries, [{"company": "function health", "human_override": "P0", "override_reason": "x"}],
        decided_date=DATE, decided_at_gate=GATE)
    assert out[0]["scoring"] == before                           # Rule 8 — scores write-once
    assert entries[0]["decision"]["human_override"] is None      # input not mutated (works on a copy)


def test_apply_is_idempotent():
    entries = [_entry()]
    decisions = [{"company": "function health", "human_override": "P1", "override_reason": "r"}]
    once = ledger.apply_decisions(entries, decisions, decided_date=DATE, decided_at_gate=GATE)
    twice = ledger.apply_decisions(once, decisions, decided_date="2026-08-01", decided_at_gate="later")
    assert len(twice[0]["decision"]["history"]) == 1            # unchanged CSV -> no new history


def test_clearing_an_override_reverts_to_model_and_records_history():
    entries = ledger.apply_decisions(
        [_entry()], [{"company": "function health", "human_override": "P1", "override_reason": "r"}],
        decided_date=DATE, decided_at_gate=GATE)
    reverted = ledger.apply_decisions(
        entries, [{"company": "function health", "human_override": "", "override_reason": ""}],
        decided_date="2026-08-01", decided_at_gate="later")
    dec = reverted[0]["decision"]
    assert dec["human_override"] is None
    assert ledger.final_priority(reverted[0]) == "P3"           # back to model_priority
    assert [h["to"] for h in dec["history"]] == ["P1", None]


def test_reason_only_edit_records_history():
    entries = ledger.apply_decisions(
        [_entry()], [{"company": "function health", "human_override": "P1", "override_reason": "first"}],
        decided_date=DATE, decided_at_gate=GATE)
    out = ledger.apply_decisions(
        entries, [{"company": "function health", "human_override": "P1", "override_reason": "sharper reason"}],
        decided_date="2026-08-01", decided_at_gate="later")
    hist = out[0]["decision"]["history"]
    assert hist[-1]["field"] == "override_reason" and hist[-1]["to"] == "sharper reason"


def test_unknown_company_raises():
    with pytest.raises(ledger.LedgerError):
        ledger.apply_decisions([_entry()], [{"company": "ghost co", "human_override": "P1"}],
                               decided_date=DATE, decided_at_gate=GATE)


def test_invalid_tier_raises():
    with pytest.raises(ledger.LedgerError):
        ledger.apply_decisions([_entry()], [{"company": "function health", "human_override": "P9"}],
                               decided_date=DATE, decided_at_gate=GATE)


def test_full_round_trip_through_disk(tmp_path):
    entries = [_entry(), _entry("zoe", model_priority="P2", floor_ok=True, human_override=None)]
    ledger_path = tmp_path / "ledger.jsonl"
    ledger.execute_ledger_write(ledger_path, entries)

    cards_path = tmp_path / "cards.csv"
    ledger.write_cards_csv(cards_path, entries)

    decisions = ledger.read_cards_csv(cards_path)                # simulate Katelynd opening the CSV
    fh = next(d for d in decisions if d["company"] == "function health")
    fh["human_override"] = "P1"
    fh["override_reason"] = "revenue + complexity"

    applied = ledger.apply_decisions(entries, decisions, decided_date=DATE, decided_at_gate=GATE)
    ledger.execute_ledger_write(ledger_path, applied)

    reopened = ledger.read_ledger(ledger_path)
    by_company = {e["company"]: e for e in reopened}
    assert ledger.final_priority(by_company["function health"]) == "P1"
    assert ledger.provenance(by_company["function health"]) == "human-overridden"
    assert ledger.final_priority(by_company["zoe"]) == "P2"      # untouched -> model-accepted
    assert ledger.provenance(by_company["zoe"]) == "model-accepted"
