"""Commit 8 — end-to-end test for the R1 orchestration (`research_runner.run_r1`) with a FAKE client.

Exercises the full live path deterministically: classifier + growth + bg_fit reads (canned), floor-
eligibility, the N=5 loop (bg_fit re-run each pass), and revalidate_r1 resolution. A bg_fit WOBBLE on one
company must flag it (tier_variance); a floored (professional) company must cost ZERO bg/growth calls.
No real LLM.
"""

import json

import pandas as pd

from health_tech_research_agent import research_runner as rr
from health_tech_research_agent import structured_evidence as se


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
         "outcomes_finding": "good", "payer_institutional_finding": "", "growth_finding": "grew"},
        {"company": "season health", "fit_brief_json": json.dumps(_fit_brief(inst=True)),
         "operating_characteristics_finding": "daily nutrition", "commercial_scale_finding": "health plans",
         "outcomes_finding": "good", "payer_institutional_finding": "in-network covered lives",
         "growth_finding": "grew"},
        {"company": "medforce", "fit_brief_json": json.dumps(_fit_brief()),
         "operating_characteristics_finding": "clinician tool", "commercial_scale_finding": "scaled",
         "outcomes_finding": "good", "payer_institutional_finding": "", "growth_finding": "grew"},
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
            kind = "reset"
            text = json.dumps({"reset_events": []})    # series-b companies: reset irrelevant to gating
        elif "who_uses" in prompt:                     # §B2 classifier
            kind, who = "classifier", ("professional", "institution") if company == "medforce" else (
                "consumer", "mixed" if company == "season health" else "consumer")
            text = json.dumps({"who_uses": who[0], "who_pays": who[1], "who_uses_confidence": "high"})
        elif "BACKGROUND FIT" in prompt:               # §B5 bg_fit
            kind = "bg"
            if company == "season health":             # the wobble: 8/3 alternating -> floor-wobbler
                seq = self.outer.season_bg
                val = seq[self.outer.season_i % len(seq)]
                self.outer.season_i += 1
            else:
                val = 8
            text = json.dumps({"background_fit": val, "data_feedback_loop": "no", "basis": "x"})
        else:                                          # §B6 growth
            kind = "growth"
            text = json.dumps({"kind": "rate", "rate_pct": 60, "source": "company"})
        self.outer.calls.append((kind, company))
        return type("R", (), {"output_text": text})()


class _FakeClient:
    def __init__(self):
        self.calls = []
        self.season_bg = [8, 3, 8, 3, 8]
        self.season_i = 0
        self.responses = _FakeResponses(self)


def test_run_r1_end_to_end_flags_wobble_and_floors_professional():
    client = _FakeClient()
    rep = rr.run_r1(_df(), client=client, n=5)

    # report shape + full roster resolved
    assert set(rep["resolved"]) == {"acme", "season health", "medforce"}
    assert sum(rep["tally"].values()) == 3

    # the professional company is floored P3, deterministically
    assert rep["resolved"]["medforce"]["final_priority"] == "P3"

    # season's bg_fit wobbled (8/3) -> tier MOVES across runs -> flagged; acme stable -> not flagged
    assert "season health" in rep["tier_variance"]
    assert rep["resolved"]["season health"]["tier_variance"] is True
    assert rep["resolved"]["acme"]["tier_variance"] is False


def test_run_r1_spends_no_llm_on_floored_company():
    client = _FakeClient()
    rr.run_r1(_df(), client=client, n=5)
    # medforce (professional) gets the once-per-company reset re-emit + classifier, then NEVER bg/growth-scored
    med_calls = [k for (k, co) in client.calls if co == "medforce"]
    assert med_calls == ["reset", "classifier"]
    # the two eligible companies get bg_fit on each of the 5 passes
    assert sum(1 for (k, co) in client.calls if k == "bg" and co == "acme") == 5
    assert sum(1 for (k, co) in client.calls if k == "bg" and co == "season health") == 5


def test_run_r1_detail_exposes_components_per_run():
    client = _FakeClient()
    rep = rr.run_r1(_df(), client=client, n=5)
    # detail carries the per-run component scores for diagnosis (bug vs drift vs data-change)
    season = rep["detail"]["season health"]
    assert len(season) == 5
    assert season[0]["bg_fit"] == 8 and season[1]["bg_fit"] == 3   # the wobble is visible
    for run in season:
        assert set(run) >= {"tier", "final", "bg_fit", "pmf", "strain", "stage"}


def test_run_r1_reads_classifier_and_base_growth_once():
    client = _FakeClient()
    rr.run_r1(_df(), client=client, n=5)
    # reset re-emit + classifier: exactly once per company (3 each); base growth once for each eligible
    assert sum(1 for (k, _) in client.calls if k == "reset") == 3
    assert sum(1 for (k, _) in client.calls if k == "classifier") == 3
    # growth: 2 base + 5 R2 re-runs for season (acme is not an R2 case) = 7
    assert sum(1 for (k, _) in client.calls if k == "growth") == 7
