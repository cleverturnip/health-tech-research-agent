"""Commit 8 (v1.22) — end-to-end test for the CACHING R1 orchestration (`research_runner.run_r1` /
`take_r1_reads` / `score_r1_from_cache`) with a FAKE client.

Exercises the full path deterministically: each of the four reads (classifier + hardened reset + growth +
bg_fit) is taken ONCE per company and cached; scoring reads OFF the cache. Verifies: reproducibility by
construction (score twice off the cache -> identical), each read taken once (no N passes), a floored
(professional) company costs zero bg/growth, and the bounded review_set. No real LLM.
"""

import json

import pandas as pd

from health_tech_research_agent import research_runner as rr


def _fit_brief(*, revenue="$60M ARR", inst=False):
    return {
        "commercial_evidence": {"revenue_or_arr": revenue, "user_scale_signal": "",
                                "growth_signal": "growing", "business_model_type": "payer" if inst else "d2c"},
        "maturity_evidence": {"funding_rounds": [{"type": "series-b", "series_designation": "series-b",
                                                  "date": "2023-01", "is_priced_equity": True}],
                              "ipo_event": {}, "ipo_status": "private"},
        "capability_evidence": {"a2_score": 60},
        "reset_evidence": {"reset_events": []},
    }


def _df():
    return pd.DataFrame([
        {"company": "acme", "fit_brief_json": json.dumps(_fit_brief()),
         "operating_characteristics_finding": "daily habit", "commercial_scale_finding": "scaled",
         "outcomes_finding": "good", "payer_institutional_finding": "", "growth_finding": "grew",
         "org_events_finding": ""},
        {"company": "season health", "fit_brief_json": json.dumps(_fit_brief(inst=True)),
         "operating_characteristics_finding": "daily nutrition", "commercial_scale_finding": "health plans",
         "outcomes_finding": "good", "payer_institutional_finding": "in-network covered lives",
         "growth_finding": "grew", "org_events_finding": ""},
        {"company": "medforce", "fit_brief_json": json.dumps(_fit_brief()),
         "operating_characteristics_finding": "clinician tool", "commercial_scale_finding": "scaled",
         "outcomes_finding": "good", "payer_institutional_finding": "", "growth_finding": "grew",
         "org_events_finding": ""},
    ])


class _FakeResponses:
    def __init__(self, outer):
        self.outer = outer

    def create(self, **kwargs):
        prompt = kwargs["input"]
        company = ""
        for line in prompt.splitlines():
            if line.strip().lower().startswith("company:"):
                company = line.split(":", 1)[1].strip().lower()
                break
        if "reset_events" in prompt:                   # §B4 hardened reset re-emitter
            kind, text = "reset", json.dumps({"reset_events": []})
        elif "who_uses" in prompt:                     # §B2 classifier
            who = ("professional", "institution") if company == "medforce" else (
                "consumer", "mixed" if company == "season health" else "consumer")
            kind = "classifier"
            text = json.dumps({"who_uses": who[0], "who_pays": who[1], "who_uses_confidence": "high"})
        elif "BACKGROUND FIT" in prompt:               # §B5 bg_fit — a STABLE read per company (temp-0-free)
            kind, val = "bg", (6 if company == "season health" else 8)
            text = json.dumps({"background_fit": val, "data_feedback_loop": "no", "basis": "x"})
        else:                                          # §B6 growth
            kind, text = "growth", json.dumps({"kind": "rate", "rate_pct": 60, "source": "company"})
        self.outer.calls.append((kind, company))
        return type("R", (), {"output_text": text})()


class _FakeClient:
    def __init__(self):
        self.calls = []
        self.responses = _FakeResponses(self)


def test_run_r1_end_to_end_report_shape_and_floor():
    client = _FakeClient()
    rep = rr.run_r1(_df(), client=client)
    assert set(rep["resolved"]) == {"acme", "season health", "medforce"}
    assert sum(rep["tally"].values()) == 3
    # the professional company floors -> P3, and carries a floor_reason (never wrong-and-silent)
    assert rep["resolved"]["medforce"]["final_priority"] == "P3"
    assert rep["resolved"]["medforce"]["floor_reason"]
    assert "medforce" in rep["review_set"]


def test_run_r1_reads_taken_once_each_no_n_passes():
    client = _FakeClient()
    rr.run_r1(_df(), client=client)
    # each read taken exactly ONCE per company (no N=5 loop): 3 reset + 3 classifier
    assert sum(1 for (k, _) in client.calls if k == "reset") == 3
    assert sum(1 for (k, _) in client.calls if k == "classifier") == 3
    # eligible companies (acme, season) get ONE bg + ONE growth each; medforce (floored) gets none
    assert sum(1 for (k, _) in client.calls if k == "bg") == 2
    assert sum(1 for (k, _) in client.calls if k == "growth") == 2
    assert [k for (k, co) in client.calls if co == "medforce"] == ["reset", "classifier"]


def test_run_r1_reproducible_off_cache_no_recall():
    client = _FakeClient()
    rep1 = rr.run_r1(_df(), client=client)
    calls_after_first = len(client.calls)
    # re-run with the returned cache -> scores off the frozen reads, ZERO new LLM calls, identical result
    rep2 = rr.run_r1(_df(), client=client, cache=rep1["cache"])
    assert len(client.calls) == calls_after_first          # nothing re-called behind the scorer
    assert rep1["resolved"] == rep2["resolved"]            # reproducible by construction
    assert rep1["tally"] == rep2["tally"]


def test_run_r1_score_from_cache_is_pure_and_identical():
    client = _FakeClient()
    df = _df()
    cache = rr.take_r1_reads(df, client=client)
    r1 = rr.score_r1_from_cache(df, cache)
    r2 = rr.score_r1_from_cache(df, cache)
    assert [x["final_priority"] for x in r1] == [x["final_priority"] for x in r2]


def test_run_r1_refresh_retakes_only_named_company():
    client = _FakeClient()
    rep = rr.run_r1(_df(), client=client)
    base = len(client.calls)
    rr.run_r1(_df(), client=client, cache=rep["cache"], refresh=["season health"])
    # only season's reads are re-taken; acme + medforce reused
    refreshed = [co for (_, co) in client.calls[base:]]
    assert set(refreshed) == {"season health"}


def test_run_r1_review_set_is_reported_with_size():
    client = _FakeClient()
    rep = rr.run_r1(_df(), client=client)
    assert rep["review_set_size"] == len(rep["review_set"])
    assert isinstance(rep["review_set"], dict)
