"""Phase-3 GATE-1 Step 1 — grounding + prompt builders (offline, on the sample fixture)."""

from pathlib import Path

from health_tech_research_agent import ledger
from health_tech_research_agent.webapp import gate1

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"


def _entries():
    return ledger.read_ledger(FIXTURE)


def test_grounding_payload_has_the_four_parts():
    payload = gate1.grounding_payload(_entries(), "early-stage metabolic health")
    assert payload["thesis"] == "early-stage metabolic health"
    # exclude list = every researched company
    for company in ["alpha health", "beta health", "gamma health"]:
        assert company in payload["researched"]
    # roster: one compact line per company with the scores
    assert "FINAL" in payload["roster"] and "alpha health" in payload["roster"]
    assert payload["roster"].count("\n") == len(_entries()) - 1     # one line per company


def test_grounding_overrides_carry_reason_and_direction():
    # beta health is overridden P3 -> P1 in the fixture
    payload = gate1.grounding_payload(_entries(), "x")
    assert "beta health" in payload["overrides"]
    assert "model said" in payload["overrides"] and "she set" in payload["overrides"]


def test_empty_thesis_falls_back():
    payload = gate1.grounding_payload(_entries(), "   ")
    assert payload["thesis"] == "(no thesis saved yet)"


def test_build_system_prompt_fills_all_placeholders():
    prompt = gate1.build_system_prompt(_entries(), "my thesis text")
    assert "my thesis text" in prompt
    assert "USE WEB SEARCH" in prompt                                # locked wording present
    assert "{thesis}" not in prompt and "{roster}" not in prompt     # every placeholder filled
    assert "do NOT propose any of these again" in prompt
