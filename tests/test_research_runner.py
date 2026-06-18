"""Tests for the migrated research runner (Slice 1, Commit 1).

Covers the faithfully-extracted functions only (call_openai, the four search
functions, the taxonomy wrapper, the fit-brief prompt builder, and
run_company_fit_brief). The batch loop + per-company recovery is Commit 2.

All tests run offline with no API key: the OpenAI client is a fake that records
what would be sent and returns scripted output. Retry/exception tests monkeypatch
the module's exception names so they pass whether or not the openai SDK is
installed (call_openai resolves those names from module globals at runtime).
"""

import pytest

from health_tech_research_agent import research_runner as rr


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, text):
        self.output_text = text


class ScriptedClient:
    """Stands in for the OpenAI client.

    ``client.responses.create(**kwargs)`` pops the next scripted item: an
    Exception instance is raised; anything else is returned as ``output_text``.
    Every call's kwargs are recorded for assertions.
    """

    def __init__(self, script=None):
        self._script = list(script) if script is not None else ["{}"]
        self.calls = []

    @property
    def responses(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._script.pop(0) if self._script else "{}"
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


class RecordingClient(ScriptedClient):
    """Convenience: always returns '{}' and exposes the last sent prompt."""

    @property
    def last_prompt(self):
        return self.calls[-1]["input"]


# ---------------------------------------------------------------------------
# call_openai — request shape
# ---------------------------------------------------------------------------


def test_call_openai_returns_output_text_and_request_shape():
    client = ScriptedClient(["the answer"])
    out = rr.call_openai("hello", client=client, model="m1", max_output_tokens=123)
    assert out == "the answer"
    assert len(client.calls) == 1
    kwargs = client.calls[0]
    assert kwargs["model"] == "m1"
    assert kwargs["input"] == "hello"
    assert kwargs["max_output_tokens"] == 123
    # web search OFF by default -> no tools wiring
    assert "tools" not in kwargs
    assert "tool_choice" not in kwargs


def test_call_openai_enables_web_search_tool_when_requested():
    client = ScriptedClient(["ok"])
    rr.call_openai("q", client=client, model="m", use_web_search=True)
    kwargs = client.calls[0]
    assert kwargs["tools"] == [{"type": "web_search"}]
    assert kwargs["tool_choice"] == "auto"


def test_call_openai_default_model_and_tokens():
    client = ScriptedClient(["ok"])
    rr.call_openai("q", client=client)
    kwargs = client.calls[0]
    assert kwargs["model"] == rr.DEFAULT_MODEL
    assert kwargs["max_output_tokens"] == 500


# ---------------------------------------------------------------------------
# call_openai — retry semantics (faithful: RateLimit retries, APIError raises)
# ---------------------------------------------------------------------------


def test_call_openai_retries_rate_limit_then_succeeds(monkeypatch):
    class FakeRateLimit(Exception):
        pass

    monkeypatch.setattr(rr, "RateLimitError", FakeRateLimit)

    client = ScriptedClient([FakeRateLimit(), FakeRateLimit(), "recovered"])
    sleeps = []

    out = rr.call_openai("q", client=client, sleep_fn=sleeps.append)

    assert out == "recovered"
    assert len(client.calls) == 3
    # waits are 90 * attempt for attempts 1 and 2; attempt 3 succeeds (no wait)
    assert sleeps == [90, 180]


def test_call_openai_raises_runtime_error_when_retries_exhausted(monkeypatch):
    class FakeRateLimit(Exception):
        pass

    monkeypatch.setattr(rr, "RateLimitError", FakeRateLimit)

    client = ScriptedClient([FakeRateLimit(), FakeRateLimit(), FakeRateLimit()])
    sleeps = []

    with pytest.raises(RuntimeError, match="Max retries reached"):
        rr.call_openai("q", client=client, sleep_fn=sleeps.append)

    assert len(client.calls) == 3
    assert sleeps == [90, 180, 270]


def test_call_openai_api_error_raises_immediately_no_retry(monkeypatch):
    class FakeRateLimit(Exception):
        pass

    class FakeAPIError(Exception):
        pass

    monkeypatch.setattr(rr, "RateLimitError", FakeRateLimit)
    monkeypatch.setattr(rr, "APIError", FakeAPIError)

    client = ScriptedClient([FakeAPIError("boom"), "would-be-recovery"])
    sleeps = []

    with pytest.raises(FakeAPIError):
        rr.call_openai("q", client=client, sleep_fn=sleeps.append)

    # raised on the first attempt, did not retry, did not sleep
    assert len(client.calls) == 1
    assert sleeps == []


def test_call_openai_respects_max_retries_argument(monkeypatch):
    class FakeRateLimit(Exception):
        pass

    monkeypatch.setattr(rr, "RateLimitError", FakeRateLimit)

    client = ScriptedClient([FakeRateLimit(), "ok"])
    sleeps = []

    out = rr.call_openai("q", client=client, max_retries=2, sleep_fn=sleeps.append)
    assert out == "ok"
    assert sleeps == [90]


# ---------------------------------------------------------------------------
# Search functions — route to call_openai with web search + correct token caps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func, max_tokens, anchor, none_line",
    [
        (rr.search_funding, 300, "latest credible funding, valuation, stage", "No strong public funding evidence found."),
        (rr.search_payer_signal, 350, "institutional distribution traction", "No strong public institutional signal found."),
        (rr.search_outcomes, 350, "credible outcomes, clinical, behavioral", "No strong public outcomes evidence found."),
        (rr.search_commercial_scale, 450, "commercial scale, revenue quality", "No strong public commercial scale evidence found."),
    ],
)
def test_search_functions_request_shape_and_interpolation(func, max_tokens, anchor, none_line):
    client = RecordingClient()
    func("ACME (acme.example)", client=client, model="m")
    kwargs = client.calls[0]
    assert kwargs["model"] == "m"
    assert kwargs["max_output_tokens"] == max_tokens
    assert kwargs["tools"] == [{"type": "web_search"}]  # web search ON for research
    prompt = kwargs["input"]
    assert anchor in prompt
    assert 'say "' + none_line + '"' in prompt
    assert "ACME (acme.example)" in prompt  # research_query interpolated


def test_search_commercial_scale_preserves_special_characters():
    """Lock the curly quotes and the multiplication sign that the audit-sensitive
    commercial prompt depends on (transcription-fidelity guard)."""
    client = RecordingClient()
    rr.search_commercial_scale("X", client=client)
    prompt = client.calls[0]["input"]
    assert "vague “fast-growing” claims" in prompt   # U+201C / U+201D
    assert "paid customers × pricing" in prompt           # U+00D7
    assert "customer count × pricing" in prompt


# ---------------------------------------------------------------------------
# Fit-brief prompt builder — fidelity anchors + interpolation placement
# ---------------------------------------------------------------------------


def test_build_fit_brief_prompt_structure_and_interpolation():
    prompt = rr.build_fit_brief_prompt("Acme Health", "FINDINGS-BLOB", "TAXONOMY-BLOCK")

    # opening line
    assert prompt.startswith(
        "\nYou are evaluating a health tech company for Katelynd LaVallee's job search."
    )
    # the three interpolations land in the right places
    assert "Company:\nAcme Health\n" in prompt
    assert "Latest research findings:\nFINDINGS-BLOB\n" in prompt
    assert "Controlled taxonomy instructions:\nTAXONOMY-BLOCK\n" in prompt
    # company also appears inside the JSON schema
    assert '"company": "Acme Health"' in prompt

    # the five scored fields, in the scores block, unchanged
    for key in [
        "thesis_fit_score",
        "pmf_scale_score",
        "evidence_confidence_score",
        "katelynd_role_fit_score",
        "operator_timing_score",
    ]:
        assert key in prompt

    # structural markers that downstream parsing depends on
    assert "Return ONLY valid JSON. No markdown. No commentary outside JSON." in prompt
    assert "Use this JSON schema exactly:" in prompt
    assert '"role_timing_assessment": {' in prompt
    assert '"scale_signal_assessment": {' in prompt
    assert '"company_maturity_read": "early / early-growth / scale-up / late-stage / public / unclear"' in prompt

    # f-string brace-escapes rendered correctly ({{ -> {, }} -> })
    assert prompt.rstrip().endswith("}")
    assert "{{" not in prompt and "}}" not in prompt

    # the curly-quote guardrail line is preserved verbatim
    assert "vague “fast-growing” claims" in prompt


def test_build_fit_brief_prompt_is_pure_and_repeatable():
    a = rr.build_fit_brief_prompt("C", "F", "T")
    b = rr.build_fit_brief_prompt("C", "F", "T")
    assert a == b  # no hidden state / I/O


# ---------------------------------------------------------------------------
# run_company_fit_brief — synthesis call shape (web search OFF, 6500 tokens)
# ---------------------------------------------------------------------------


def test_run_company_fit_brief_call_shape_with_supplied_block():
    client = ScriptedClient(['{"company": "Acme"}'])
    out = rr.run_company_fit_brief(
        "Acme",
        "findings",
        client=client,
        model="m",
        taxonomy_prompt_block="SENTINEL-BLOCK",
    )
    assert out == '{"company": "Acme"}'
    kwargs = client.calls[0]
    assert kwargs["max_output_tokens"] == 6500
    assert "tools" not in kwargs  # synthesis does NOT use web search
    assert "SENTINEL-BLOCK" in kwargs["input"]
    assert "Acme" in kwargs["input"]


def test_run_company_fit_brief_loads_taxonomy_when_block_not_supplied(monkeypatch):
    captured = {}

    def fake_loader(taxonomy_dir):
        captured["dir"] = taxonomy_dir
        return "LOADED-TAX-BLOCK"

    monkeypatch.setattr(rr, "load_taxonomy_prompt_block_for_fit_brief", fake_loader)
    client = ScriptedClient(["{}"])

    rr.run_company_fit_brief("Acme", "findings", client=client, taxonomy_dir="/some/dir")

    assert captured["dir"] == "/some/dir"
    assert "LOADED-TAX-BLOCK" in client.calls[0]["input"]


# ---------------------------------------------------------------------------
# Taxonomy wrapper — real block on success, faithful fallback on failure
# ---------------------------------------------------------------------------


def test_load_taxonomy_block_returns_real_block_for_repo_taxonomy():
    from pathlib import Path

    taxonomy_dir = Path(__file__).resolve().parents[1] / "taxonomy"
    block = rr.load_taxonomy_prompt_block_for_fit_brief(taxonomy_dir)
    assert isinstance(block, str) and block.strip()
    assert not block.startswith("CONTROLLED HEALTH-TECH TAXONOMY UNAVAILABLE")


def test_load_taxonomy_block_falls_back_when_builder_raises(monkeypatch):
    import health_tech_research_agent.taxonomy as taxonomy_mod

    def boom(_dir):
        raise RuntimeError("no taxonomy here")

    monkeypatch.setattr(taxonomy_mod, "build_taxonomy_prompt_block", boom)

    block = rr.load_taxonomy_prompt_block_for_fit_brief("/nonexistent")
    assert block.startswith("CONTROLLED HEALTH-TECH TAXONOMY UNAVAILABLE")
    assert "no taxonomy here" in block
