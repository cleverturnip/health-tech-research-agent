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


# --- Step 2: the discovery call ---------------------------------------------

import types  # noqa: E402


class _FakeResponses:
    def __init__(self, text, calls):
        self._text, self._calls = text, calls

    def create(self, **kwargs):
        self._calls.append(kwargs)
        return types.SimpleNamespace(output_text=self._text)


class _FakeClient:
    def __init__(self, text):
        self.calls = []
        self.responses = _FakeResponses(text, self.calls)


def test_parse_candidates_extracts_block_and_strips_it():
    text = ('Here are a few ideas!\n\n```candidates\n'
            '[{"company":"Acme Health","why":"daily engagement","signal":"Series A, $14M"}]\n```')
    display, cands = gate1.parse_candidates(text)
    assert display == "Here are a few ideas!"
    assert cands == [{"company": "Acme Health", "why": "daily engagement", "signal": "Series A, $14M"}]


def test_parse_candidates_no_block_and_malformed():
    assert gate1.parse_candidates("just chatting, no companies yet") == ("just chatting, no companies yet", [])
    display, cands = gate1.parse_candidates("text\n```candidates\nnot json{{\n```")
    assert cands == []                                               # malformed -> empty, never raises


def test_drop_researched_catches_exact_and_suffix_variants():
    entries = [{"company": "Levels Health"}, {"company": "Culina Health"}]
    candidates = [{"company": "Levels"}, {"company": "Culina Health"}, {"company": "Bevel"}]
    kept, dropped = gate1.drop_researched(candidates, entries)
    assert [c["company"] for c in kept] == ["Bevel"]          # only the genuinely-new one survives
    assert set(dropped) == {"Levels", "Culina Health"}        # exact + trailing-"Health" variant both caught


def test_discover_calls_openai_with_web_search_and_returns_candidates():
    reply = ('Try these.\n```candidates\n[{"company":"Beta Co","why":"w","signal":"s"}]\n```')
    client = _FakeClient(reply)
    out = gate1.discover(client, "SYSTEM PROMPT HERE",
                         [{"role": "user", "content": "early-stage metabolic health"}])
    assert out["reply"] == "Try these."
    assert out["candidates"] == [{"company": "Beta Co", "why": "w", "signal": "s"}]
    call = client.calls[0]
    assert call["tools"] == [{"type": "web_search"}]                 # web search enabled
    assert "SYSTEM PROMPT HERE" in call["instructions"]              # system prompt passed
    assert call["input"][0]["content"] == "early-stage metabolic health"
