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
# call_openai — empty-output guard (item 8)
# ---------------------------------------------------------------------------


def test_call_openai_empty_output_retries_bumped_then_returns_marker():
    client = ScriptedClient(["", ""])  # blank twice (original budget + bumped retry)
    out = rr.call_openai("q", client=client, model="m", max_output_tokens=400)
    assert out == rr.SEARCH_FAILED_MARKER
    assert out != ""                                    # never a silent empty
    assert "No strong public" not in out                # never the false 'none found' sentinel
    assert len(client.calls) == 2                        # exactly one retry
    assert client.calls[0]["max_output_tokens"] == 400
    assert client.calls[1]["max_output_tokens"] == 600   # bumped ×1.5 — counters the cause


def test_call_openai_whitespace_only_output_counts_as_blank():
    client = ScriptedClient(["   \n  ", "  "])           # whitespace-only is blank
    out = rr.call_openai("q", client=client, model="m", max_output_tokens=400)
    assert out == rr.SEARCH_FAILED_MARKER


def test_call_openai_bumped_retry_recovers():
    client = ScriptedClient(["", "real summary text"])  # blank, then the bumped retry succeeds
    out = rr.call_openai("q", client=client, model="m", max_output_tokens=400)
    assert out == "real summary text"
    assert len(client.calls) == 2
    assert client.calls[1]["max_output_tokens"] == 600


def test_call_openai_populated_output_does_not_retry():
    client = ScriptedClient(["hello"])
    out = rr.call_openai("q", client=client, model="m", max_output_tokens=400)
    assert out == "hello"
    assert len(client.calls) == 1                        # no empty-output retry


def test_is_search_failure_predicate():
    assert rr.is_search_failure(rr.SEARCH_FAILED_MARKER) is True
    assert rr.is_search_failure("No strong public funding evidence found.") is False
    assert rr.is_search_failure("") is False
    assert rr.is_search_failure("real evidence text") is False


def _complete_research_row():
    return {col: "x" for col in REQUIRED_RESEARCH_COLUMNS}


def test_row_is_complete_basic():
    assert rr._row_is_complete(_complete_research_row()) is True
    blank = _complete_research_row()
    blank["outcomes_finding"] = ""
    assert rr._row_is_complete(blank) is False


def test_row_is_complete_treats_failure_marker_as_incomplete():
    # A marker is a FAILED search, not a real finding: the row must read INCOMPLETE so resume
    # re-researches it (visible AND auto-retried — not silently baked in as 'complete').
    row = _complete_research_row()
    row["funding_finding"] = rr.SEARCH_FAILED_MARKER
    assert rr._row_is_complete(row) is False


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
        (rr.search_funding, 700, "latest credible funding, valuation, stage", "No strong public funding evidence found."),
        (rr.search_payer_signal, 700, "institutional distribution traction", "No strong public institutional signal found."),
        (rr.search_outcomes, 700, "credible outcomes, clinical, behavioral", "No strong public outcomes evidence found."),
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
        "funding_rounds",
        "ipo_event",
        "ipo_status",
        "founding_year",
        "last_raise_date",
        "last_raise_amount",
        "total_funding",
        "funding_stage_evidence",
    ]:
        assert f'"{field}":' in prompt
    # B-rec (v1.2): the LLM gathers rounds and NEVER emits funding_stage (a code mapper derives it)
    assert '"funding_stage":' not in prompt
    # the maturity-revenue separation backstop, stated in the prompt (Function fix)
    assert "do NOT infer rounds from headcount, revenue" in prompt
    assert "still a series-b round (NOT a higher stage)" in prompt


def test_prompt_has_commercial_evidence_and_four_redflags():
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert '"commercial_evidence": {' in prompt
    for field in [
        "revenue_or_arr",
        "paying_customer_count",
        "sponsored_user_scale",
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
    # sponsored_user_scale (SOT B6.1 v1.3): secondary signal, structurally barred from the score
    assert "NEVER feeds growth_signal OR growth_score" in prompt


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
    # the build-mandate vs defensive-reaction poles (v1.15 wording)
    assert "needs a senior operator to BUILD" in prompt
    assert "DEFENSIVE reaction" in prompt
    # restructuring-layoffs is not pre-judged — the opening question decides (per-event)
    assert "do NOT prejudge it; the opening question for THIS event decides" in prompt
    # the strategic-pivot strengthening (v1.15): "transformation"/"evolution"/"pivotal" can't upgrade a pivot
    assert 'strategic-pivot EVEN IF framed as a "transformation," "evolution," or "pivotal" moment' in prompt
    assert '"Changed/added what we sell or how we price/sell it" = strategic-pivot' in prompt
    assert '"rebuilding how we operate internally" = declared-transformation' in prompt
    # v1.15/v1.16 additions: ipo-prep type + the structural-role exec-add rule
    assert "ipo-prep — IPO preparation" in prompt
    assert "EXEC ADD — read the opening by STRUCTURAL ROLE" in prompt


def test_prompt_reset_multi_event_per_event_framing():
    # Slice 3.5: list each event, answer opening PER EVENT, don't let one bury another
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert "List EACH distinct event as its own object in reset_events" in prompt
    assert "answer the opening question PER EVENT" in prompt
    assert "do NOT let one event's nature determine another's" in prompt
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

    Distinguishes web searches (kwargs carry ``tools`` — incl. the commercial
    recovery passes) from the revenue presence check (no ``tools``, detected by its
    "PRESENT or ABSENT" prompt) from the fit brief (no ``tools``). It detects which
    company a call is for by finding a company name inside the prompt, then:
      * search calls -> return a short finding string;
      * presence-check calls -> return "PRESENT" (observability only);
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
        if "tools" in kwargs:  # any web search (incl. the commercial recovery passes)
            return FakeResponse(f"finding for {company}")
        if "PRESENT or ABSENT" in prompt:  # the revenue presence check (observability only)
            return FakeResponse("PRESENT")
        # otherwise the fit-brief synthesis call
        if company in self.fail_on:
            raise self.fail_exc
        if company in self.bad_json_for:
            return FakeResponse("not json at all {oops")
        return FakeResponse('{"company": "%s", "priority_level": "P2"}' % company)

    def fitbrief_inputs(self):
        return [
            c["input"]
            for c in self.calls
            if "tools" not in c and "PRESENT or ABSENT" not in c["input"]
        ]


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
        wait_between_passes=3,
        sleep_fn=sleeps.append,
    )

    # per company: funding is now a recovery too. Each recovery contributes (N-1) inter-pass waits of 3
    # then an after-wait of 7; the single searches (payer, outcomes) + after-org + trailing are 7 each.
    # (operating has no trailing wait; synthesis none.) Order: funding, payer, outcomes, commercial,
    # growth, paying, org, trailing.
    def _recovery_waits(n):
        return [3] * (n - 1) + [7]
    per_company = (
        _recovery_waits(rr.FUNDING_RECOVERY_PASSES)
        + [7, 7]                                       # payer, outcomes
        + _recovery_waits(rr.REVENUE_RECOVERY_PASSES)
        + _recovery_waits(rr.GROWTH_RECOVERY_PASSES)
        + _recovery_waits(rr.PAYING_RECOVERY_PASSES)
        + [7, 7]                                       # after-org, trailing
    )
    assert sleeps == per_company * 2


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
    (the coverage-audit gap), at the 700-token ceiling (raised from 400 for item 8 —
    funding is a rich-topic search that also hit the empty-output budget exhaustion)."""
    client = RecordingClient()
    rr.search_funding("X", client=client, model="m")
    kwargs = client.calls[0]
    prompt = kwargs["input"]
    assert kwargs["max_output_tokens"] == 700
    assert "founding year" in prompt                          # added field (was uncovered)
    assert "FACT LIST" in prompt
    assert "Tag each fact with its source name and date." in prompt
    # B-rec (v1.2): search GATHERS the dated rounds; a deterministic mapper picks funding_stage
    assert "DATED funding-round sequence" in prompt
    assert "priced equity round" in prompt
    assert "do NOT compute or pick a single funding_stage" in prompt
    assert "date-unknown" in prompt


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


def test_build_latest_status_findings_has_eight_labeled_sections():
    out = rr._build_latest_status_findings("F", "P", "O", "C", "G", "PC", "OE", "OC")
    for label in (
        "Funding:",
        "Payer / institutional signal:",
        "Outcomes:",
        "Commercial scale / revenue quality:",
        "Revenue growth / dated revenue endpoints:",
        "Paying-customer count:",
        "Recent org / leadership events",
        "Operating characteristics",
    ):
        assert label in out
    assert "G" in out and "PC" in out                        # growth + paying recovery unions carried
    assert "OE" in out and "OC" in out                       # the two operator findings are carried


def test_batch_runs_searches_and_persists_operator_findings(tmp_path):
    """The loop runs all searches per company and persists the new finding columns.
    Funding, commercial, growth-rate AND paying-count are each recoveries now."""
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme"])
    run_research_batch(["Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep)
    search_calls = [c for c in client.calls if "tools" in c]
    # 4 single (payer/outcomes/org/operating) + funding/commercial/growth/paying recoveries
    expected = (4 + rr.FUNDING_RECOVERY_PASSES + rr.REVENUE_RECOVERY_PASSES
                + rr.GROWTH_RECOVERY_PASSES + rr.PAYING_RECOVERY_PASSES)
    assert len(search_calls) == expected
    df = pd.read_csv(ckpt)
    for col in ("org_events_finding", "operating_characteristics_finding"):
        assert col in df.columns
        assert str(df.iloc[0][col]).strip() != ""


def test_batch_commercial_uses_recovery_union_and_resume_is_idempotent(tmp_path):
    """Step 5 wiring: commercial_scale_finding is the N=5 recovery UNION; a completed
    company is skipped on resume with zero new calls (resume/idempotency unchanged)."""
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme"])
    run_research_batch(["Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep)

    commercial = pd.read_csv(ckpt).iloc[0]["commercial_scale_finding"]
    # all five passes are unioned into the one finding (pass 1 general + 4 source-directed)
    assert "pass1 (general)" in commercial
    assert "pass5 (source-directed)" in commercial
    n_passes = commercial.count("(general)") + commercial.count("(source-directed)")
    assert n_passes == 5

    # resume: Acme already complete -> skipped, NOTHING re-researched (no new API calls)
    client2 = BatchClient(companies=["Acme"])
    result2 = run_research_batch(
        ["Acme"], client=client2, checkpoint_path=ckpt, sleep_fn=_noop_sleep
    )
    assert result2.reused == ["Acme"]
    assert result2.completed == []
    assert client2.calls == []  # idempotent resume: search_with_recovery NOT re-invoked


def test_batch_growth_recovery_union_persisted_and_feeds_synthesis(tmp_path):
    """FRAMEWORK_VERSION v1.1 wiring: growth-rate gets its OWN N=5 recovery union
    (growth-directed retries), persisted as growth_finding and fed to the synthesis as
    the 'Revenue growth / dated revenue endpoints' section."""
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme"])
    run_research_batch(["Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep)

    growth = pd.read_csv(ckpt).iloc[0]["growth_finding"]
    n_passes = growth.count("(general)") + growth.count("(source-directed)")
    assert n_passes == 5                                     # always-run-N=5 union (pass1 + 4 retries)
    # the growth union reaches the synthesis as its own labeled section
    fit_inputs = "\n".join(client.fitbrief_inputs())
    assert "Revenue growth / dated revenue endpoints:" in fit_inputs


def test_batch_paying_recovery_union_persisted_and_feeds_synthesis(tmp_path):
    """FRAMEWORK_VERSION v1.2 wiring: paying-count gets its OWN N=5 recovery union
    (paying-directed retries), persisted as paying_finding and fed to the synthesis as
    the 'Paying-customer count' section."""
    ckpt = tmp_path / "c.csv"
    client = BatchClient(companies=["Acme"])
    run_research_batch(["Acme"], client=client, checkpoint_path=ckpt, sleep_fn=_noop_sleep)

    paying = pd.read_csv(ckpt).iloc[0]["paying_finding"]
    n_passes = paying.count("(general)") + paying.count("(source-directed)")
    assert n_passes == 5                                     # always-run-N=5 union (pass1 + 4 retries)
    # the paying union reaches the synthesis as its own labeled section
    fit_inputs = "\n".join(client.fitbrief_inputs())
    assert "Paying-customer count:" in fit_inputs


def test_fit_brief_reset_emitter_classifies_by_substance():
    """Reset emitter (v1.15): the synthesis is the SINGLE emitter — it CLASSIFIES BY SUBSTANCE from the
    org-events facts (re-classifying press framing), NOT a transcribe-the-search's-label step. The old
    'carry through / do not re-derive' instruction is what let sword's 'evolution' and oura's S-1 fire,
    so it is intentionally REVERSED here."""
    prompt = rr.build_fit_brief_prompt("Acme", "FINDINGS", "TAX")
    assert "Recent org / leadership events" in prompt           # still points at the org-events findings
    assert "CLASSIFY BY SUBSTANCE, NOT PRESS FRAMING" in prompt
    assert "re-classifying how the source framed it" in prompt
    # the old transcribe / don't-re-derive instruction is GONE (the substance-classify shift)
    assert "do NOT re-derive or override the opening here" not in prompt
    assert "carry each event's event_type and opening read through" not in prompt


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


# ---------------------------------------------------------------------------
# search_with_recovery — always-run-N + union (generic mechanism, Step 1)
# ---------------------------------------------------------------------------


def _stub_search(text):
    """A search_fn double that ignores the client and returns fixed text, so the
    client.calls count reflects only the source-directed retry passes."""

    def _search(research_query, *, client, model):
        return text

    return _search


def _retry_builder(query):
    return f"source-directed retry for {query}"


def _present(union_text, *, client, model):
    return True


def _absent(union_text, *, client, model):
    return False


def test_search_with_recovery_always_runs_n_passes_and_unions():
    client = ScriptedClient(["pass2 text", "pass3 text"])  # passes 2 and 3
    union, prov = rr.search_with_recovery(
        _stub_search("pass1 text"),
        "Acme Health",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=3,
    )
    assert len(client.calls) == 2  # passes 2,3 hit the client; pass 1 is stubbed
    assert all(s in union for s in ("pass1 text", "pass2 text", "pass3 text"))
    assert prov.n_passes == 3
    assert prov.field_name == "revenue"
    assert prov.figure_present is True


def test_search_with_recovery_runs_all_passes_even_when_pass1_has_content():
    # No early stop: pass 1 "finding" a figure does NOT short-circuit the rest.
    client = ScriptedClient(["p2", "p3", "p4"])
    _union, prov = rr.search_with_recovery(
        _stub_search("pass1 has $150M run-rate"),
        "Acme",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=4,
    )
    assert len(client.calls) == 3  # passes 2,3,4 all ran
    assert prov.n_passes == 4


def test_search_with_recovery_retry_passes_use_web_search():
    client = ScriptedClient(["p2", "p3"])
    rr.search_with_recovery(
        _stub_search("p1"),
        "Acme",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=3,
    )
    for call in client.calls:  # every retry pass is a web search
        assert call["tools"] == [{"type": "web_search"}]
        assert call["tool_choice"] == "auto"


def test_search_with_recovery_union_preserves_conflicting_figures():
    client = ScriptedClient(["$150M run-rate (CB Insights)", "no revenue disclosed"])
    union, _prov = rr.search_with_recovery(
        _stub_search("$115.9M revenue (Latka)"),
        "Midi",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=3,
    )
    assert "115.9" in union and "150M" in union  # both legitimate figures kept


def test_search_with_recovery_excludes_failed_passes_from_union():
    client = ScriptedClient([rr.SEARCH_FAILED_MARKER, "pass3 real text"])
    union, _prov = rr.search_with_recovery(
        _stub_search("pass1 real text"),
        "Acme",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=3,
    )
    assert rr.SEARCH_FAILED_MARKER not in union
    assert "pass1 real text" in union and "pass3 real text" in union
    assert not rr.is_search_failure(union)


def test_search_with_recovery_returns_marker_when_all_passes_fail():
    client = ScriptedClient([rr.SEARCH_FAILED_MARKER, rr.SEARCH_FAILED_MARKER])
    union, prov = rr.search_with_recovery(
        _stub_search(rr.SEARCH_FAILED_MARKER),
        "Ghost",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,  # would say present, but all-failed short-circuits first
        field_name="revenue",
        n_passes=3,
    )
    assert union == rr.SEARCH_FAILED_MARKER
    assert rr.is_search_failure(union)
    assert prov.figure_present is False


def test_search_with_recovery_presence_check_is_observability_only():
    def run(presence_check):
        client = ScriptedClient(["p2", "p3"])
        union, prov = rr.search_with_recovery(
            _stub_search("p1"),
            "Acme",
            client=client,
            model="m",
            retry_prompt_builder=_retry_builder,
            presence_check=presence_check,
            field_name="revenue",
            n_passes=3,
        )
        return union, prov, len(client.calls)

    union_t, prov_t, calls_t = run(_present)
    union_f, prov_f, calls_f = run(_absent)
    assert union_t == union_f  # union content identical regardless of presence verdict
    assert calls_t == calls_f == 2  # pass count identical
    assert prov_t.figure_present is True and prov_f.figure_present is False


def test_search_with_recovery_sleeps_between_passes_when_configured():
    sleeps = []
    client = ScriptedClient(["p2", "p3", "p4"])
    rr.search_with_recovery(
        _stub_search("p1"),
        "Acme",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=4,
        wait_between_passes=9,
        sleep_fn=sleeps.append,
    )
    assert sleeps == [9, 9, 9]  # one wait before each of the 3 retry passes (2,3,4)


def test_search_with_recovery_no_sleep_when_wait_is_zero():
    sleeps = []
    client = ScriptedClient(["p2", "p3"])
    rr.search_with_recovery(
        _stub_search("p1"),
        "Acme",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=3,
        wait_between_passes=0,
        sleep_fn=sleeps.append,
    )
    assert sleeps == []  # zero wait -> no sleep calls (the mechanism-defeating value)


def test_search_with_recovery_provenance_carries_raw_passes():
    client = ScriptedClient(["p2", "p3"])
    _union, prov = rr.search_with_recovery(
        _stub_search("p1"),
        "Acme",
        client=client,
        model="m",
        retry_prompt_builder=_retry_builder,
        presence_check=_present,
        field_name="revenue",
        n_passes=3,
    )
    # raw per-pass findings, so the harness can SEE independence (not infer it)
    assert prov.passes == ["p1", "p2", "p3"]


# ---------------------------------------------------------------------------
# Revenue config: source-directed retry prompt + presence check (Step 2)
# ---------------------------------------------------------------------------


def test_revenue_source_directed_prompt_leads_but_does_not_filter():
    prompt = rr.revenue_source_directed_prompt("Midi Health (midihealth.com)")
    assert "Midi Health (midihealth.com)" in prompt  # query interpolated
    for src in ("CB Insights", "Latka", "Growjo", "PitchBook", "Sacra"):
        assert src in prompt  # leads with the aggregators
    assert "LEAD, NOT a filter" in prompt
    # Gate-2 hardening: company-disclosed figures wherever they live, never restricted
    low = prompt.lower()
    assert "press release" in low
    assert "crowdcube" in low  # the ZOE recovery source
    assert "founder" in low and "interview" in low
    assert "do not restrict" in low


def test_revenue_source_directed_prompt_has_url_targeting_and_alias_handling():
    # B1: direct-URL targeting + alias/former-name handling, framed as ADDITIVE (not a filter).
    prompt = rr.revenue_source_directed_prompt("Pelago (pelago.health), formerly Quit Genius")
    low = prompt.lower()
    # direct-URL patterns for the named aggregators (reliability boost on pages we know exist)
    assert "getlatka.com/companies/" in low
    assert "cbinsights.com/company/" in low
    # alias / former-name handling (the Pelago/Quit Genius, Join-X miss class)
    assert "former name" in low
    assert "alias" in low
    # ADDITIVE framing — must NOT become the filter we rejected (Gate-2 softening)
    assert "in addition to, not instead of" in low
    # off-aggregator company-disclosed figures still required, incl. statutory filings (ZOE/Companies House)
    assert "companies house" in low or "statutory filing" in low


def test_prompt_entity_carry_and_flag_rule():
    # B2: plausible-alias -> carry + flag (queryable field); clear mismatch -> drop; prefer carry when unsure.
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert '"entity_review_needed"' in prompt  # dedicated queryable field in the schema
    assert "possible-alias" in prompt
    assert "PLAUSIBLE alias" in prompt
    assert "CLEAR mismatch" in prompt
    assert "(entity-uncertain: possible alias of" in prompt
    assert "NEVER silently omit" in prompt
    assert "PREFER carry+flag over silent drop" in prompt


def test_build_summary_surfaces_entity_review_needed_field():
    # B2: the flag must be a QUERYABLE column (routes to manual review), not buried free-text.
    import json

    from health_tech_research_agent.review import build_summary

    fit_present = json.dumps(
        {
            "entity_review_needed": "possible-alias",
            "commercial_evidence": {
                "revenue_or_arr": "$82.3M (entity-uncertain: possible alias of ZOE — verify)"
            },
        }
    )
    fit_absent = json.dumps({"commercial_evidence": {"revenue_or_arr": "$10M"}})
    df = pd.DataFrame(
        [
            {"company": "ZOE", "fit_brief_json": fit_present},
            {"company": "Other", "fit_brief_json": fit_absent},
        ]
    )
    summary = build_summary(df)
    assert "entity_review_needed" in summary.columns  # queryable/filterable column
    by_company = dict(zip(summary["company"], summary["entity_review_needed"]))
    assert by_company["ZOE"] == "possible-alias"
    assert by_company["Other"] == ""  # additive default; no false flags


# ---------------------------------------------------------------------------
# Group 1 field configs: growth-rate + paying-customer-count
# ---------------------------------------------------------------------------


def test_growth_rate_source_directed_prompt():
    prompt = rr.growth_rate_source_directed_prompt("Pelago (pelago.health), formerly Quit Genius")
    assert "Pelago (pelago.health), formerly Quit Genius" in prompt
    low = prompt.lower()
    assert "quantified" in low and "growth rate" in low
    # Tightening 1: a rate is only usable WITH its time period
    assert "time period" in low
    assert "not a usable rate" in low
    assert "period unclear" in low
    # source-directed URL targeting + lead-not-filter + alias (B1 principles)
    assert "getlatka.com/companies/" in low
    assert "in addition to, not instead of" in low
    assert "former name" in low and "alias" in low
    # refine-to-derive: [1] compute-don't-just-report + [2] mandatory show-the-inputs / never bare + DERIVED tag
    assert "compute the rate" in low
    assert "show the inputs" in low
    assert "never emit a bare" in low
    assert "derived-by-you" in low
    # FENCE (FRAMEWORK_VERSION v1.2 / SOT B6.1): revenue or PAID-user growth ONLY; headcount/employee,
    # partner/client-count, funding, and non-paying user/MAU/download growth are excluded
    assert "paid-user growth rate" in low                # :688 tightened (no loose "revenue/user")
    assert "headcount/" in low and "employee/team growth" in low
    assert "partner/client-count growth" in low


def test_growth_rate_presence_check_requires_period_and_parses():
    client = RecordingClient(["PRESENT"])
    rr.growth_rate_presence_check("$60M->$150M in 2024-2025", client=client, model="m")
    low = client.last_prompt.lower()
    assert "time period" in low  # usable rate needs a period (Tightening 1 preserved)
    assert "derived" in low and "dated revenue endpoints" in low  # (b) a derived rate counts PRESENT
    # FENCE (v1.2 / SOT B6.1): employee/headcount/funding/partner/non-paying-user growth do NOT count
    assert "employee/headcount growth" in low and "non-paying" in low
    assert "tools" not in client.calls[-1]  # no web search
    assert rr.growth_rate_presence_check("x", client=ScriptedClient(["PRESENT"]), model="m") is True
    assert rr.growth_rate_presence_check("x", client=ScriptedClient(["ABSENT"]), model="m") is False


def test_prompt_growth_signal_carries_derived_rate():
    # Companion edit 1: synthesis carries a DERIVED rate with inputs+period; never strips/bare-emits.
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert "if COMPUTED from dated endpoints, WITH its inputs and a DERIVED tag" in prompt
    assert "NEVER strip the inputs/period or emit a bare rate" in prompt
    assert "moderate-confidence source, NOT company-reported" in prompt


def test_paying_count_source_directed_prompt():
    prompt = rr.paying_count_source_directed_prompt("Pelago (pelago.health), formerly Quit Genius")
    assert "Pelago (pelago.health), formerly Quit Genius" in prompt
    low = prompt.lower()
    assert "paying" in low
    # paying-only: exclude free / covered / eligible lives
    assert "free" in low and "covered" in low and "eligible" in low
    # Tightening 2: paying employer clients belong HERE; covered/eligible lives NON-paying & distinct
    assert "employer" in low and "client" in low
    assert "3.4m eligible lives" in low  # the Pelago coexistence example, kept distinct
    # non-paying counts carried + labeled, not dropped
    assert "label them non-paying" in low
    # URL targeting + lead-not-filter + alias (B1 principles)
    assert "getlatka.com/companies/" in low
    assert "in addition" in low
    assert "former name" in low and "alias" in low


def test_paying_count_presence_check_excludes_covered_lives_and_parses():
    client = RecordingClient(["PRESENT"])
    rr.paying_count_presence_check("100,000 paying members", client=client, model="m")
    low = client.last_prompt.lower()
    assert "covered" in low and "eligible" in low  # covered/eligible lives don't count
    assert "tools" not in client.calls[-1]  # no web search
    assert rr.paying_count_presence_check("x", client=ScriptedClient(["PRESENT"]), model="m") is True
    assert rr.paying_count_presence_check("x", client=ScriptedClient(["ABSENT"]), model="m") is False


def test_funding_rounds_source_directed_prompt():
    prompt = rr.funding_rounds_source_directed_prompt("Pelago (pelago.health), formerly Quit Genius")
    assert "Pelago (pelago.health), formerly Quit Genius" in prompt
    low = prompt.lower()
    assert "most recent priced round" in low                 # the recall goal (latest round)
    assert "crunchbase" in low and "pitchbook" in low         # lead with full-history pages
    assert "in addition to, not instead of" in low           # lead-not-filter
    assert "former name" in low and "alias" in low            # alias / former-name handling
    assert "last ~24 months" in low                           # the recall window
    assert "do not compute or pick a single funding_stage" in low   # gather-not-pick (the mapper picks)


def test_funding_latest_round_presence_check_is_observability():
    client = RecordingClient(["PRESENT"])
    rr.funding_latest_round_presence_check("series-d $90M 2024", client=client, model="m")
    low = client.last_prompt.lower()
    assert "last ~24 months" in low and "priced equity round" in low
    assert "tools" not in client.calls[-1]                    # no web search (observability)
    assert rr.funding_latest_round_presence_check("x", client=ScriptedClient(["PRESENT"]), model="m") is True
    assert rr.funding_latest_round_presence_check("x", client=ScriptedClient(["ABSENT"]), model="m") is False


def test_prompt_revenue_per_user_derive_in_synthesis():
    # Group 2: rev-per-user derives in the synthesis from already-recovered revenue ÷ paying-count.
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    assert "COMPUTE it from figures already recovered" in prompt
    assert "revenue ÷ paying-customer count" in prompt
    assert "SHOW THE INPUTS" in prompt
    assert "Mark a computed value DERIVED" in prompt
    assert "Never emit a bare per-user number" in prompt


def test_revenue_presence_check_prompt_shape_and_no_web_search():
    client = RecordingClient(["PRESENT"])
    rr.revenue_presence_check(
        "--- pass1 ---\n$150M run-rate (CB Insights)", client=client, model="m"
    )
    prompt = client.last_prompt
    assert "$150M run-rate (CB Insights)" in prompt  # union included
    assert "PRESENT or ABSENT" in prompt  # asks the binary
    low = prompt.lower()
    assert "funding rounds" in low and "valuation" in low  # exclusions
    assert "paying-customers x pricing" in low  # implied-from-pricing counts as present
    assert "tools" not in client.calls[-1]  # NO web search on the presence check


def test_revenue_presence_check_parses_present_and_absent():
    assert rr.revenue_presence_check("x", client=ScriptedClient(["PRESENT"]), model="m") is True
    assert rr.revenue_presence_check("x", client=ScriptedClient(["ABSENT"]), model="m") is False
    # tolerant of trailing text / case
    assert rr.revenue_presence_check("x", client=ScriptedClient(["present — $10M"]), model="m") is True
    assert rr.revenue_presence_check("x", client=ScriptedClient(["absent, none found"]), model="m") is False


def test_search_with_recovery_with_revenue_config_end_to_end():
    # pass 1 = real search_commercial_scale; passes 2-3 = source-directed; then the
    # presence check. All four calls hit the scripted client in order.
    client = ScriptedClient(
        [
            "pass1: $115.9M revenue (Latka, 2025)",  # search_commercial_scale (pass 1)
            "pass2: $150M run-rate (CB Insights)",   # source-directed pass 2
            "pass3: no further figure",              # source-directed pass 3
            "PRESENT",                                # presence check
        ]
    )
    union, prov = rr.search_with_recovery(
        rr.search_commercial_scale,
        "Midi Health",
        client=client,
        model="m",
        retry_prompt_builder=rr.revenue_source_directed_prompt,
        presence_check=rr.revenue_presence_check,
        field_name="revenue",
        n_passes=3,
    )
    assert "115.9M" in union and "150M run-rate" in union  # union preserves both
    assert prov.figure_present is True
    assert len(client.calls) == 4  # 3 searches + 1 presence check


def test_prompt_revenue_carry_and_rate_and_multi_figure_q4():
    # Step 4: Option-A carry-and-rate surfacing + multi-figure q4 resolution.
    prompt = rr.build_fit_brief_prompt("C", "F", "T")
    # schema field surfaces ALL figures with the sanctioned type tags; empty only if none
    assert "List ALL revenue/ARR/run-rate figures found" in prompt
    assert "implied-from-pricing / weak-single-source" in prompt
    assert "Empty ONLY if NO real figure was found in any pass" in prompt
    # carry-and-rate instruction, tightened to STATED or implied-from-pricing (no open "credibly implied")
    assert "a source actually STATED, or that is implied from paying-customers × pricing" in prompt
    assert "credibly implied" not in prompt  # the over-inference phrasing must be absent
    assert "Do NOT omit a real figure for being low-quality" in prompt
    # q4 = strongest source type present, with the multiple-weak guard
    assert "STRONGEST quality among them" in prompt
    assert "Multiple weak or single-source figures do NOT promote q4" in prompt
    assert "NEVER lifts q4's source-type bucket" in prompt
    # q4's existing 3-value enum is unchanged (the deterministic Q4_STRONG_OK gate relies on it)
    assert '"q4_evidence_quality": "company-reported / credible-estimate / unverified-promotional"' in prompt
