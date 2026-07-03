"""Guard: tests/fixtures/sample_ledger.jsonl (the shared reference for the §3.4 entry shape) loads and
matches the live entry shape. If the ledger schema changes, regenerate the fixture
(`PYTHONPATH=src python3 tests/fixtures/generate_sample_ledger.py`) and this keeps it honest."""

from __future__ import annotations

from pathlib import Path

from health_tech_research_agent import ledger

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"

_TOP_LEVEL = {"company", "batch_id", "framework_version", "date_scored", "model", "stage", "stage_basis",
              "one_liner", "scoring", "gates", "model_priority", "recommended_action", "override_candidate",
              "flags", "decision"}


def test_sample_ledger_loads_and_matches_entry_shape():
    entries = ledger.read_ledger(FIXTURE)
    assert len(entries) == 5
    by = {e["company"]: e for e in entries}

    for entry in entries:                                    # every entry carries the full §3.4 top level
        assert _TOP_LEVEL <= set(entry), f"{entry['company']} missing {_TOP_LEVEL - set(entry)}"
        assert set(entry["scoring"]) >= {"bg_fit", "pmf", "strain", "final_score", "floor_rule"}
        assert set(entry["decision"]) >= {"human_override", "override_reason", "history"}

    beta = by["beta health"]                                 # override applied -> decision + history + derived
    assert ledger.final_priority(beta) == "P1" and ledger.provenance(beta) == "human-overridden"
    assert beta["decision"]["history"][-1]["to"] == "P1"

    gamma = by["gamma health"]                               # B2B floor -> bg + FINAL are n/a
    assert gamma["model"] == "B2B" and gamma["scoring"]["bg_fit"]["score"] is None
    assert gamma["scoring"]["final_score"] is None

    assert "+reset" in by["delta health"]["gates"]["agency"]["detail"]   # agency passed via a reset
    assert ledger.provenance(by["alpha health"]) == "model-accepted"     # clean P0, no override
