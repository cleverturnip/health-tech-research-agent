"""Ledger persistence tests (Commit C) — JSONL round-trip + the transactional write (backup / read-back /
rollback), mirroring the master_update discipline (Rule 4/5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from health_tech_research_agent import ledger


def _entry(company, tier="P0", final=20):
    return {"company": company, "model_priority": tier,
            "scoring": {"final_score": final, "bg_fit": {"score": 8, "loop": True}},
            "flags": [], "decision": {"human_override": None, "history": []}}


def test_write_read_roundtrip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    entries = [_entry("alpha"), _entry("bravo", "P3", 10)]
    ledger.write_ledger(path, entries)
    assert ledger.read_ledger(path) == entries


def test_read_missing_returns_empty(tmp_path):
    assert ledger.read_ledger(tmp_path / "nope.jsonl") == []


def test_write_is_one_json_object_per_line(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.write_ledger(path, [_entry("alpha"), _entry("bravo")])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["company"] == "alpha"


def test_read_rejects_malformed_line(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"company": "alpha"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ledger.LedgerError):
        ledger.read_ledger(path)


def test_read_rejects_non_object_line(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"company": "alpha"}\n[1, 2, 3]\n', encoding="utf-8")
    with pytest.raises(ledger.LedgerError):
        ledger.read_ledger(path)


def test_transaction_rejects_duplicate_companies(tmp_path):
    path = tmp_path / "ledger.jsonl"
    with pytest.raises(ledger.LedgerError):
        ledger.execute_ledger_write(path, [_entry("alpha"), _entry("Alpha")])
    assert not path.exists()          # refused BEFORE writing


def test_transaction_writes_and_reads_back(tmp_path):
    path = tmp_path / "ledger.jsonl"
    result = ledger.execute_ledger_write(path, [_entry("alpha"), _entry("bravo")])
    assert result.readback_ok is True and result.entries_written == 2
    assert result.backup_path == ""   # nothing to back up on first write
    assert ledger.read_ledger(path) == [_entry("alpha"), _entry("bravo")]


def test_transaction_backs_up_existing(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.execute_ledger_write(path, [_entry("alpha")])
    result = ledger.execute_ledger_write(path, [_entry("alpha"), _entry("bravo")])
    assert result.backup_path and Path(result.backup_path).exists()
    assert ledger.read_ledger(result.backup_path) == [_entry("alpha")]   # backup holds the prior state


def test_transaction_rolls_back_on_readback_mismatch(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    ledger.execute_ledger_write(path, [_entry("alpha")])          # durable prior state

    # Force the read-back to disagree with what was written -> the transaction must roll back to the backup.
    monkeypatch.setattr(ledger, "read_ledger", lambda p: [])
    with pytest.raises(ledger.LedgerError):
        ledger.execute_ledger_write(path, [_entry("bravo")])

    monkeypatch.undo()
    assert ledger.read_ledger(path) == [_entry("alpha")]          # rolled back to the prior state
