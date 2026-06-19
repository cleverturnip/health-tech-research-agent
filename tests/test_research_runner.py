"""Tests for the migrated research runner (Slice 1, Commit 1).

Covers the faithfully-extracted functions only (call_openai, the four search
functions, the taxonomy wrapper, the fit-brief prompt builder, and
run_company_fit_brief). The batch loop + per-company recovery is Commit 2.

All tests run offline with no API key: the OpenAI client is a fake that records
what would be sent and returns scripted output. Retry/exception tests monkeypatch
the module's exception names so they pass whether or not the openai SDK is
installed (call_openai resolves those names from module globals at runtime).
"""

import pandas as pd
import pytest

from health_tech_research_agent import research_runner as rr
from health_tech_research_agent.research_runner import (
    REQUIRED_RESEARCH_COLUMNS,
    run_research_batch,
)


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
    # Slice 2: the LLM no longer emits the maturity/commercial JUDGMENTS as output
    # fields (it emits the evidence instead); these are derived deterministically.
    assert '"company_maturity_read":' not in prompt
    assert '"commercial_scale_signal":' not in prompt

    # f-string brace-escapes rendered correctly ({{ -> {, }} -> })
    assert prompt.rstrip().endswith("}")
    assert "{{" not in prompt and "}}" not in prompt

    # the curly-quote guardrail line is preserved verbatim
    assert "vague “fast-growing” claims" in prompt


# ---------------------------------------------------------------------------
# Slice 2 — structured-evidence prompt fields (maturity + commercial)
# ---------------------------------------------------------------------------


def test_prompt_has_maturity_evidence_block():
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert '"maturity_evidence": {' in prompt
    for field in [
        "funding_stage",
        "ipo_status",
        "founding_year",
        "last_raise_date",
        "last_raise_amount",
        "total_funding",
        "funding_stage_evidence",
    ]:
        assert f'"{field}":' in prompt
    # the maturity-revenue separation backstop, stated in the prompt (Function fix)
    assert "do NOT infer a stage from headcount, revenue" in prompt
    assert 'still funding_stage = "series-b"' in prompt


def test_prompt_has_commercial_evidence_and_four_redflags():
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert '"commercial_evidence": {' in prompt
    for field in [
        "revenue_or_arr",
        "paying_customer_count",
        "revenue_per_user",
        "growth_signal",
        "business_model_type",
        "funding_evidence",
    ]:
        assert f'"{field}":' in prompt
    for q in ["q1_acquisition", "q2_monetization", "q3_funding_dependent", "q4_evidence_quality"]:
        assert f'"{q}":' in prompt
    # funding is structurally excluded; q3 phrased as the counterfactual (Solace catch)
    assert "structurally excluded" in prompt
    assert "setting the funding/valuation story aside" in prompt


def test_prompt_q4_evidence_quality_anchors():
    # the Function case depends on credible-estimate vs unverified-promotional being crisp
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert "company-reported" in prompt
    assert "credible-estimate" in prompt
    assert "unverified-promotional" in prompt
    assert "Sacra" in prompt
    assert "CB Insights" in prompt


def test_prompt_drops_llm_maturity_and_commercial_judgment_fields():
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    # removed as OUTPUT fields (prose references in the priority-gate guidance may remain)
    assert '"company_maturity_read":' not in prompt
    assert '"commercial_scale_signal":' not in prompt
    assert '"commercial_scale_signal_reason":' not in prompt
    # institutional + outcomes signals are out of Slice 2 scope and remain
    assert '"institutional_distribution_signal":' in prompt
    assert '"outcomes_signal":' in prompt


# ---------------------------------------------------------------------------
# Slice 3 — reset / restructure researched field
# ---------------------------------------------------------------------------


def test_prompt_has_reset_evidence_block():
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    # Slice 3.5: reset_evidence is now a LIST of per-event objects
    assert '"reset_evidence": {' in prompt
    assert '"reset_events": [' in prompt
    for field in ["event_type", "basis", "creates_high_agency_opening"]:
        assert f'"{field}":' in prompt
    # the event-type vocabulary is offered to the LLM
    for et in [
        "leadership-change", "declared-transformation", "founder-transition",
        "post-failure-rebuild", "restructuring-layoffs", "strategic-pivot", "ma-integration",
    ]:
        assert et in prompt
    # the single-value field names are gone (replaced by per-event objects)
    assert '"reset_event_type":' not in prompt
    assert '"reset_basis":' not in prompt
    assert '"reset_creates_high_agency_opening":' not in prompt


def test_prompt_reset_vs_pivot_framing():
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    # the forward-mandate vs defensive-reaction poles, both concrete
    assert "FORWARD-LOOKING MANDATE" in prompt
    assert "DEFENSIVE reaction" in prompt
    # restructuring-layoffs is not pre-judged — the opening question decides (now per-event)
    assert "do NOT prejudge it; the opening question for THIS event decides" in prompt
    # the strategic-pivot strengthening: a "transformation" framing can't upgrade a pivot
    assert 'strategic-pivot EVEN IF the company frames it as a "transformation"' in prompt
    assert '"Changed what we sell" = strategic-pivot' in prompt
    assert '"rebuilding how we operate" = declared-transformation' in prompt


def test_prompt_reset_multi_event_per_event_framing():
    # Slice 3.5: list each event, answer opening PER EVENT, don't let one bury another
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert "List EACH distinct event as its own object in reset_events" in prompt
    assert "answer the opening question PER EVENT" in prompt
    assert "Do NOT let one event's nature determine another's" in prompt
    assert "a loud pivot must NOT hide a restructuring that IS an opening" in prompt
    assert "return an empty list" in prompt


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


# ===========================================================================
# run_research_batch (Commit 2) — loop, per-company recovery, checkpointing
# ===========================================================================


class BatchClient:
    """Fake OpenAI client for batch tests.

    Distinguishes the four web searches (kwargs carry ``tools``) from the fit
    brief (no ``tools``). It detects which company a call is for by finding a
    company name inside the prompt, then:
      * search calls -> return a short finding string;
      * fit-brief calls -> return minimal valid JSON, UNLESS the company is in
        ``fail_on`` (raise ``fail_exc``) or ``bad_json_for`` (return non-JSON).
    Use company names that are not substrings of one another (e.g. Acme / Beta).
    """

    def __init__(self, *, companies, fail_on=(), bad_json_for=(), fail_exc=None):
        self.companies = list(companies)
        self.fail_on = set(fail_on)
        self.bad_json_for = set(bad_json_for)
        self.fail_exc = fail_exc or RuntimeError("API down")
        self.calls = []

    @property
    def responses(self):
        return self

    def _company_in(self, prompt):
        for name in self.companies:
            if name in prompt:
                return name
        return None

    def create(self, **kwargs):
        self.calls.append(kwargs)
        prompt = kwargs["input"]
        company = self._company_in(prompt)
        if "tools" in kwargs:  # one of the four research searches
            return FakeResponse(f"finding for {company}")
        # otherwise the fit-brief synthesis call
        if company in self.fail_on:
            raise self.fail_exc
        if company in self.bad_json_for:
            return FakeResponse("not json at all {oops")
        return FakeResponse('{"company": "%s", "priority_level": "P2"}' % company)

    def fitbrief_inputs(self):
        return [c["input"] for c in self.calls if "tools" not in c]


def _seed_complete_checkpoint(path, company):
    """Write a checkpoint with one fully-complete (all 7 columns non-blank) row."""
    row = {
        col: (company if col == "company" else f"{col}-value")
        for col in REQUIRED_RESEARCH_COLUMNS
    }
    pd.DataFrame([row]).to_csv(path, index=False)


def _noop_sleep(_seconds):
    return None


# --- primary recovery proof: A succeeds, B fails -> loop continues -----------


def test_batch_recovers_from_failure_completed_a_failed_b(tmp_path):
    ckpt = tmp_path / "batch_checkpoint.csv"
    client = BatchClient(companies=["Acme", "Beta"], fail_on=["Beta"])

    result = run_research_batch(
        ["Acme", "Beta"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep
    )

    assert result.completed == ["Acme"]
    assert "Beta" in result.failed
    assert "RuntimeError" in result.failed["Beta"]
    assert result.reused == []

    # checkpoint persisted A only; B (failed) is absent -> retried on resume
    df = pd.read_csv(ckpt)
    assert df["company"].tolist() == ["Acme"]
    for col in REQUIRED_RESEARCH_COLUMNS:
        assert col in df.columns
        assert str(df.iloc[0][col]).strip() != ""


def test_batch_continues_when_first_company_fails(tmp_path):
    """Failure of the FIRST company must not stop a later company being researched."""
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Beta", "Acme"], fail_on=["Beta"])

    result = run_research_batch(
        ["Beta", "Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep
    )

    assert result.completed == ["Acme"]
    assert list(result.failed) == ["Beta"]
    assert pd.read_csv(ckpt)["company"].tolist() == ["Acme"]


# --- bad JSON is a per-company failure under validate_json (default) ---------


def test_batch_bad_json_is_a_per_company_failure(tmp_path):
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme", "Beta"], bad_json_for=["Beta"])

    result = run_research_batch(
        ["Acme", "Beta"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep
    )

    assert result.completed == ["Acme"]
    assert "Beta" in result.failed
    assert pd.read_csv(ckpt)["company"].tolist() == ["Acme"]


def test_batch_validate_json_false_stores_unparseable_output(tmp_path):
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme", "Beta"], bad_json_for=["Beta"])

    result = run_research_batch(
        ["Acme", "Beta"],
        client=client,
        checkpoint_path=ckpt,
        sleep_fn=_noop_sleep,
        validate_json=False,
    )

    assert set(result.completed) == {"Acme", "Beta"}
    assert result.failed == {}
    assert set(pd.read_csv(ckpt)["company"]) == {"Acme", "Beta"}


# --- faithful resume ---------------------------------------------------------


def test_batch_resume_skips_completed_company(tmp_path):
    ckpt = tmp_path / "c.csv"
    _seed_complete_checkpoint(ckpt, "Acme")
    client = BatchClient(companies=["Acme", "Beta"])

    result = run_research_batch(
        ["Acme", "Beta"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep
    )

    assert result.reused == ["Acme"]
    assert result.completed == ["Beta"]
    # Acme was NOT researched at all: no API call mentions it
    assert [c for c in client.calls if "Acme" in c["input"]] == []
    # only one fit-brief call happened, and it was for Beta
    assert len(client.fitbrief_inputs()) == 1
    assert "Beta" in client.fitbrief_inputs()[0]
    # checkpoint now carries both the seeded A and the new B
    assert set(pd.read_csv(ckpt)["company"]) == {"Acme", "Beta"}


# --- happy path: checkpoint + mirror, faithful 7-column schema ---------------


def test_batch_happy_path_writes_checkpoint_and_mirror(tmp_path):
    ckpt = tmp_path / "local.csv"
    mirror = tmp_path / "drive" / "mirror.csv"
    client = BatchClient(companies=["Acme", "Beta"])

    result = run_research_batch(
        ["Acme", "Beta"],
        client=client,
        checkpoint_path=ckpt,
        mirror_checkpoint_path=mirror,
        sleep_fn=_noop_sleep,
    )

    assert result.completed == ["Acme", "Beta"]
    assert result.reused == [] and result.failed == {}
    assert result.checkpoint_path == str(ckpt)

    for path in (ckpt, mirror):
        df = pd.read_csv(path)
        assert df["company"].tolist() == ["Acme", "Beta"]
        assert list(df.columns) == REQUIRED_RESEARCH_COLUMNS  # faithful schema + order
        assert df["fit_brief_json"].str.contains("priority_level").all()


# --- faithful sleep cadence --------------------------------------------------


def test_batch_preserves_faithful_sleeps(tmp_path):
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme", "Beta"])
    sleeps = []

    run_research_batch(
        ["Acme", "Beta"],
        client=client,
        checkpoint_path=ckpt,
        wait_between_searches=7,
        sleep_fn=sleeps.append,
    )

    # per successful company: 3 waits between the 4 searches + 1 trailing wait
    assert sleeps == [7] * 8


# --- KeyboardInterrupt / SystemExit propagate (not caught as Exception) ------


def test_batch_keyboard_interrupt_propagates(tmp_path):
    ckpt = tmp_path / "c.csv"

    class InterruptingClient(BatchClient):
        def create(self, **kwargs):
            self.calls.append(kwargs)
            raise KeyboardInterrupt()

    client = InterruptingClient(companies=["Acme"])

    with pytest.raises(KeyboardInterrupt):
        run_research_batch(
            ["Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep
        )


# --- dict company items route research_query to the searches -----------------


def test_batch_accepts_dict_company_items(tmp_path):
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme"])
    items = [{"company": "Acme", "research_query": "Acme (acme.example) health"}]

    result = run_research_batch(
        items, client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep
    )

    assert result.completed == ["Acme"]
    search_inputs = [c["input"] for c in client.calls if "tools" in c]
    assert search_inputs and all("acme.example" in s for s in search_inputs)


def test_batch_returns_research_batch_result_type(tmp_path):
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme"])
    result = run_research_batch(
        ["Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep
    )
    assert isinstance(result, rr.ResearchBatchResult)
