"""Phase 1 — the GATE-2 review stamp (§1a enforcement primitive).

`finalize_gate2_review` marks EVERY entry reviewed at gate-2 close; `is_reviewed` reads it. The dashboard
refuses any entry where `is_reviewed` is False (presence in the dashboard ⟹ reviewed). The stamp lands in the
decision block only — never scores/gates (Rule 8).
"""

import copy

from health_tech_research_agent import ledger


def _entry(company, *, human_override=None, reviewed_date=None):
    """A minimal ledger-shaped entry for the stamp tests."""
    return {
        "company": company,
        "model_priority": "P3",
        "scoring": {"final_score": 12, "bg_fit": {"score": 6}},
        "gates": {"path": {"passed": True}},
        "decision": {"human_override": human_override, "reviewed_date": reviewed_date},
    }


def test_is_reviewed_false_before_stamp():
    assert ledger.is_reviewed(_entry("alpha")) is False
    assert ledger.is_reviewed({"decision": {}}) is False
    assert ledger.is_reviewed({}) is False


def test_finalize_stamps_every_entry_reviewed():
    entries = [_entry("alpha"), _entry("beta", human_override="P1")]
    stamped = ledger.finalize_gate2_review(entries, reviewed_date="2026-07-03", reviewed_at_gate="gate2_batch01")

    assert all(ledger.is_reviewed(e) for e in stamped)
    for e in stamped:
        assert e["decision"]["reviewed_date"] == "2026-07-03"
        assert e["decision"]["reviewed_at_gate"] == "gate2_batch01"


def test_finalize_does_not_mutate_input():
    entries = [_entry("alpha")]
    before = copy.deepcopy(entries)
    ledger.finalize_gate2_review(entries, reviewed_date="2026-07-03", reviewed_at_gate="g")
    assert entries == before
    assert ledger.is_reviewed(entries[0]) is False


def test_finalize_touches_only_the_decision_block():
    """Rule 8: scores/gates/model_priority are never modified by the review stamp."""
    entry = _entry("alpha", human_override="P1")
    [stamped] = ledger.finalize_gate2_review([entry], reviewed_date="2026-07-03", reviewed_at_gate="g")

    assert stamped["scoring"] == entry["scoring"]
    assert stamped["gates"] == entry["gates"]
    assert stamped["model_priority"] == entry["model_priority"]
    assert stamped["decision"]["human_override"] == "P1"  # existing decision preserved


def test_refinalize_refreshes_the_stamp():
    entries = ledger.finalize_gate2_review([_entry("alpha")], reviewed_date="2026-07-03", reviewed_at_gate="g1")
    again = ledger.finalize_gate2_review(entries, reviewed_date="2026-08-01", reviewed_at_gate="g2")
    assert again[0]["decision"]["reviewed_date"] == "2026-08-01"
    assert again[0]["decision"]["reviewed_at_gate"] == "g2"


def test_stamp_survives_round_trip_write(tmp_path):
    """The stamp is durable — it reads back through write_ledger/read_ledger."""
    entries = ledger.finalize_gate2_review([_entry("alpha")], reviewed_date="2026-07-03", reviewed_at_gate="g")
    path = tmp_path / "ledger.jsonl"
    ledger.write_ledger(path, entries)
    [reopened] = ledger.read_ledger(path)
    assert ledger.is_reviewed(reopened) is True
