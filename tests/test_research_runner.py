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
        (rr.search_funding, 400, "latest credible funding, valuation, stage", "No strong public funding evidence found."),
        (rr.search_payer_signal, 350, "institutional distribution traction", "No strong public institutional signal found."),
        (rr.search_outcomes, 350, "credible outcomes, clinical, behavioral", "No strong public outcomes evidence found."),
        (rr.search_commercial_scale, 700, "commercial scale, revenue quality", "No strong public commercial scale evidence found."),
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

    # per successful company: 5 waits between the 6 searches + 1 trailing wait
    assert sleeps == [7] * 12


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


# ---------------------------------------------------------------------------
# Slice 3.7 — new operator/organizational searches
# (search_org_events feeds reset; search_operating_characteristics feeds capability-fit)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func", [rr.search_org_events, rr.search_operating_characteristics]
)
def test_operator_searches_request_shape_and_interpolation(func):
    """Both new searches route to call_openai with web search ON, the lifted 800-token
    ceiling, the model passed through, and the research_query interpolated."""
    client = RecordingClient()
    func("ACME (acme.example)", client=client, model="m")
    kwargs = client.calls[0]
    assert kwargs["model"] == "m"
    assert kwargs["max_output_tokens"] == 800            # lifted ceiling (~600-900) per Slice 3.7
    assert kwargs["tools"] == [{"type": "web_search"}]   # current-events / behavioral -> web ON
    assert "ACME (acme.example)" in kwargs["input"]      # research_query interpolated


def test_search_org_events_structure():
    """The two anti-burying guards (recency bound + multi-item list), the full Slice 3.5
    event vocabulary, the per-event opening judgment, and the explicit none-sentinel."""
    client = RecordingClient()
    rr.search_org_events("X", client=client)
    prompt = client.calls[0]["input"]

    # recency bound — keeps reset a present-moment opening (stale events excluded)
    assert "FOCUS ON THE LAST 12" in prompt

    # multi-item list — the anti-burying guard (ZOE: pivot AND restructuring)
    assert "List EACH distinct event SEPARATELY" in prompt
    assert "Return a LIST" in prompt

    # full Slice 3.5 event-type vocabulary, so the synthesis can map to reset_events
    for event_type in (
        "leadership-change",
        "founder-transition",
        "declared-transformation",
        "post-failure-rebuild",
        "restructuring-layoffs",
        "strategic-pivot",
        "ma-integration",
    ):
        assert event_type in prompt

    # per-event high-agency-opening judgment (feeds reset_evidence)
    assert "high-agency opening (yes / no / unclear)" in prompt

    # weight costly/revealed actions over PR framing — arms the soft event types
    # (declared-transformation / post-failure-rebuild) against marketing copy as a false opening
    assert "Weight COSTLY, REVEALED actions" in prompt
    assert 'branding a routine change as a "transformation" or "new chapter" is weak evidence' in prompt

    # explicit empty-result sentinel (the legitimate "no events" outcome)
    assert "No qualifying recent org/leadership events found." in prompt


def test_search_operating_characteristics_structure():
    """The approved wording's load-bearing parts: the two lenses, the engagement-vs-
    revenue evidence-weighting split, hybrid revenue handling, the structural/reported
    strain split with its strict bar, the absence-is-a-finding default, and the
    strength-tagged three-heading output."""
    client = RecordingClient()
    rr.search_operating_characteristics("X", client=client)
    prompt = client.calls[0]["input"]

    # the two lenses
    assert "(A) PRODUCT-ENGAGEMENT STRUCTURE" in prompt
    assert "(B) OPERATIONAL STRAIN" in prompt

    # "reveal, not claim" for engagement — but revenue structure is treated as reliable
    assert "company marketing only CLAIMS it." in prompt
    assert "ARE reliable" in prompt
    assert "verifiable structural fact" in prompt

    # hybrid revenue must not collapse to "has a subscription"
    assert "HYBRID" in prompt
    assert 'Do not collapse a hybrid model into "has a subscription"' in prompt

    # strain: structural vs reported, with the strict bar on soft signals
    assert "(B1) STRUCTURAL / FACTUAL signals" in prompt
    assert "(B2) REPORTED / EXPERIENTIAL signals" in prompt
    assert "MULTIPLE INDEPENDENT sources describe the SAME specific" in prompt

    # absence-is-a-finding default (the anti-noise guard)
    assert "No notable operational strain found." in prompt
    assert "Do NOT manufacture strain." in prompt

    # strength-tagged, three-heading structured output
    assert "Product-engagement:" in prompt
    assert "Operational strain — structural:" in prompt
    assert "Operational strain — reported:" in prompt
    for strength in ("STRONG", "MODERATE", "WEAK"):
        assert strength in prompt


# ---------------------------------------------------------------------------
# Slice 3.7 — re-budget of the four existing searches (drop one-bullet; richer evidence)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func",
    [rr.search_funding, rr.search_payer_signal, rr.search_outcomes, rr.search_commercial_scale],
)
def test_existing_searches_dropped_one_bullet_constraint(func):
    """The stale one-bullet / word-cap constraint is removed from all four searches."""
    client = RecordingClient()
    func("X", client=client)
    prompt = client.calls[0]["input"]
    assert "exactly 1 bullet" not in prompt
    assert "Keep under" not in prompt


def test_search_funding_gathers_fact_list_with_founding_year():
    """Funding now asks for an explicit sourced fact list including founding year
    (the coverage-audit gap), at the lifted 400-token ceiling."""
    client = RecordingClient()
    rr.search_funding("X", client=client, model="m")
    kwargs = client.calls[0]
    prompt = kwargs["input"]
    assert kwargs["max_output_tokens"] == 400
    assert "founding year" in prompt                          # added field (was uncovered)
    assert "FACT LIST" in prompt
    assert "Tag each fact with its source name and date." in prompt


def test_search_commercial_scale_gathers_provenance_and_trend():
    """Commercial (the stress case) now gathers per-figure provenance (-> q4 evidence
    quality) and trend/history (-> q1 acquisition trend), at the lifted 700-token ceiling.
    The q1-q4 judgments themselves stay in the fit-brief synthesis (A-refined)."""
    client = RecordingClient()
    rr.search_commercial_scale("X", client=client, model="m")
    kwargs = client.calls[0]
    prompt = kwargs["input"]
    assert kwargs["max_output_tokens"] == 700
    assert "SOURCE TYPE" in prompt          # provenance per figure -> q4 evidence quality
    assert "company-reported" in prompt
    assert "TREND" in prompt                # trend / history -> q1 acquisition trend


# ---------------------------------------------------------------------------
# Slice 3.7 (Commit 3) — wire 4 -> 6 findings (assembly, completeness, persistence, nudges)
# ---------------------------------------------------------------------------


def test_required_columns_grew_by_two_operator_findings_in_order():
    """REQUIRED_RESEARCH_COLUMNS gains exactly the two operator findings, grouped with the
    other *_finding columns and before fit_brief_json (so the checkpoint column order holds)."""
    assert "org_events_finding" in REQUIRED_RESEARCH_COLUMNS
    assert "operating_characteristics_finding" in REQUIRED_RESEARCH_COLUMNS
    idx = REQUIRED_RESEARCH_COLUMNS.index
    assert (
        idx("commercial_scale_finding")
        < idx("org_events_finding")
        < idx("operating_characteristics_finding")
        < idx("fit_brief_json")
    )


def test_row_is_complete_only_with_both_operator_findings():
    """The resume/completeness gate reads ALL nine columns: a pre-3.7 row (the seven old
    columns filled) is NOT complete -> re-researched; complete needs BOTH new findings."""
    row = {
        col: "x"
        for col in REQUIRED_RESEARCH_COLUMNS
        if col not in ("org_events_finding", "operating_characteristics_finding")
    }
    assert rr._row_is_complete(row) is False                 # pre-3.7 row -> re-research
    row["org_events_finding"] = "x"
    assert rr._row_is_complete(row) is False                 # one still missing
    row["operating_characteristics_finding"] = "x"
    assert rr._row_is_complete(row) is True                  # complete only with BOTH


def test_build_latest_status_findings_has_six_labeled_sections():
    out = rr._build_latest_status_findings("F", "P", "O", "C", "OE", "OC")
    for label in (
        "Funding:",
        "Payer / institutional signal:",
        "Outcomes:",
        "Commercial scale / revenue quality:",
        "Recent org / leadership events",
        "Operating characteristics",
    ):
        assert label in out
    assert "OE" in out and "OC" in out                       # the two new findings are carried


def test_batch_runs_six_searches_and_persists_operator_findings(tmp_path):
    """The loop calls all six searches per company and persists the two new finding columns."""
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme"])
    run_research_batch(["Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep)
    search_calls = [c for c in client.calls if "tools" in c]
    assert len(search_calls) == 6                            # 4 original + 2 operator
    df = pd.read_csv(ckpt)
    for col in ("org_events_finding", "operating_characteristics_finding"):
        assert col in df.columns
        assert str(df.iloc[0][col]).strip() != ""


def test_fit_brief_reset_nudge_points_at_org_events_and_does_not_rejudge():
    """Reset nudge: synthesis is pointed at the org-events section and emits the canonical
    reset_events, carrying through the search's reads WITHOUT re-judging the opening."""
    prompt = rr.build_fit_brief_prompt("Acme", "FINDINGS", "TAX")
    assert "Recent org / leadership events" in prompt
    assert "carry each event's event_type and opening read through" in prompt
    assert "do NOT re-derive or override the opening here" in prompt


def test_fit_brief_commercial_nudge_points_at_provenance_and_trend():
    """Commercial nudge: synthesis reads q4 off SOURCE TYPE and q1 off TREND; the q1-q4
    judgments stay in the synthesis (A-refined)."""
    prompt = rr.build_fit_brief_prompt("Acme", "FINDINGS", "TAX")
    assert (
        "read q4_evidence_quality off those SOURCE TYPE tags and read q1_acquisition off the TREND"
        in prompt
    )
    assert "it does not move where these are judged" in prompt


# ---------------------------------------------------------------------------
# Slice 4 (Commit 1) — capability-fit rubric (prompt block + JSON schema).
# Replaces Slice 3.7's "no capability scoring yet" boundary guard: Slice 4 now adds it.
# ---------------------------------------------------------------------------


def test_fit_brief_capability_block_and_schema():
    """Lock the capability-fit wording: three company-shape attributes, the A2
    strain-not-complexity reframe + counterintuitive flag + don't-mirror-reset, the bands,
    the null-vs-0 policy, the softened pointers, and the capability_evidence JSON object."""
    prompt = rr.build_fit_brief_prompt("Acme Health", "FINDINGS", "TAX")

    # three attributes + company-shape framing (not skills / not mandate)
    assert "Capability-fit — score THREE company-SHAPE attributes" in prompt
    assert "those are scored elsewhere; do not import them" in prompt
    assert "a1_score — PRODUCT-ENGAGEMENT STRUCTURE" in prompt
    assert "a2_score — OPERATIONAL STRAIN" in prompt
    assert "a3_score — DIGITAL CONSUMER HABITUAL-ENGAGEMENT PRODUCT" in prompt
    assert "data-driven by necessity" in prompt

    # A2 reframe: counterintuitive direction, strain-not-complexity, don't mirror reset
    assert "COUNTERINTUITIVE BUT INTENDED:" in prompt
    assert "strain is the opportunity, so MORE strain scores HIGHER" in prompt
    assert "complexity does not discriminate and must NOT drive this" in prompt
    assert "a reorg is only ONE possible strain signal among many" in prompt

    # bands
    assert "Strong 85-100" in prompt
    assert "Absent 0-29" in prompt

    # null vs 0 (the missing-attribute contract Commit 2 depends on)
    assert "Emit null for an attribute ONLY when the evidence does not let you assess it at all." in prompt
    assert "Emit 0 (Absent band) when you CAN assess the attribute" in prompt
    assert "null is for missing EVIDENCE, not for a hard judgment call" in prompt

    # softened, empty-section-tolerant pointers
    assert "where available" in prompt

    # JSON schema object + keys + the a2 gloss
    assert '"capability_evidence": {' in prompt
    for key in ('"a1_score"', '"a1_basis"', '"a2_score"', '"a2_basis"', '"a3_score"', '"a3_basis"'):
        assert key in prompt
    assert "HIGH = strained / high opportunity, LOW = smoothly-scaling" in prompt
