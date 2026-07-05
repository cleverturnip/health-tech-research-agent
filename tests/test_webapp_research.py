"""Phase-3 research runner (slice 2) — the orchestrator wiring, offline.

Tests the NEW code (job status, dedup, ledger build + merge, read-back, failure) with the client-driven
research/score step injected as a stub — the engine underneath (run_research_batch / run_r1 / build_gate2_artifacts)
is already tested elsewhere, so it is not re-driven here.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from health_tech_research_agent.webapp import research
from health_tech_research_agent.webapp.source import FixtureDashboardSource

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ledger.jsonl"
CLOCK = lambda: datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)   # noqa: E731 — fixed clock for tests


def _rec(company, **over):
    base = dict(company=company, business_model="B2C", funding_stage="series-b",
                background_fit=8, pmf=10, arr_level=10, growth=9, strain=2, final_score=20,
                path_passed=True, agency_passed=True, gate_floored=False, floor_ok=True,
                model_priority="P0", human_override=None, floored_on_bg=False, tier_review=False,
                floor_reason="", data_feedback_loop="yes", background_fit_basis="loop",
                growth_note="high(+120%)", growth_evidence="+120%", strain_strength="MODERATE",
                strain_rationale="scaling", path_detail="alive", agency_detail="in-window",
                reset_detail="none", revenue_or_arr="$80M ARR")
    base.update(over)
    return base


def _stub_research_and_score(seen_companies):
    """A fake research+score: records the companies it was handed (to assert dedup), fires progress, and returns
    a canned roster + research frame for exactly those companies."""
    def _run(companies, on_progress):
        seen_companies.extend(companies)
        roster, rows = [], []
        for company in companies:
            on_progress(company, "completed")
            roster.append(_rec(company))
            rows.append({"company": company, "funding_finding": "Seed"})
        return roster, pd.DataFrame(rows)
    return _run


def _seed(src, names):
    src.write_candidates([{"company": n, "why": "w", "signal": "s"} for n in names], date_str="2026-07-05")


def test_run_batch_researches_new_and_merges_preserving_existing(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    before = {e["company"].lower() for e in src.read_entries()}
    assert "alpha health" in before                                   # already researched in the fixture
    _seed(src, ["Brand New A", "alpha health", "Brand New B"])        # one is already in the ledger

    seen = []
    status = research.run_batch(src, work_dir=tmp_path / "jobs",
                                research_and_score=_stub_research_and_score(seen), clock=CLOCK)

    assert seen == ["Brand New A", "Brand New B"]                     # already-researched "alpha health" filtered
    assert status["state"] == "done" and status["total"] == 2 and status["completed"] == 2 and status["added"] == 2

    after = {e["company"].lower() for e in src.read_entries()}
    assert "brand new a" in after and "brand new b" in after          # new companies merged in
    assert before <= after                                            # every pre-existing entry preserved (write-once)


def test_started_event_names_current_company_without_counting(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Brand New A"])
    jobs = tmp_path / "jobs"
    seen_status = {}

    def _rs(companies, on_progress):
        on_progress(companies[0], "started")
        seen_status.update(research.read_status(jobs))        # snapshot mid-run (after "started", before "completed")
        on_progress(companies[0], "completed")
        return [_rec(companies[0])], pd.DataFrame([{"company": companies[0], "funding_finding": "Seed"}])

    research.run_batch(src, work_dir=jobs, research_and_score=_rs, clock=CLOCK)
    assert seen_status["current_company"] == "Brand New A" and seen_status["completed"] == 0   # named, not counted


def test_run_batch_persists_raw_research_for_new_companies(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Brand New A"])
    status = research.run_batch(src, work_dir=tmp_path / "jobs",
                                research_and_score=_stub_research_and_score([]), clock=CLOCK)
    assert status["state"] == "done" and "research_write_warning" not in status
    _, research_df = src.read_review_data()                          # the review card joins this
    assert research_df is not None and "Brand New A" in list(research_df["company"])


def test_research_write_abort_is_a_warning_not_a_batch_failure(tmp_path):
    # If the research-write guard fires (e.g. a corrupt research.csv), the batch must STILL succeed — the scored
    # ledger entry is the durable artifact; the abort protects existing research and is surfaced as a warning.
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Brand New A"])
    src._review_research_path().write_text("not_the_company_column\n1\n", encoding="utf-8")   # corrupt existing
    status = research.run_batch(src, work_dir=tmp_path / "jobs",
                                research_and_score=_stub_research_and_score([]), clock=CLOCK)
    assert status["state"] == "done" and status["added"] == 1        # scored work saved despite the research abort
    assert "research_write_warning" in status                        # surfaced, not silently lost
    assert src._review_research_path().read_text().startswith("not_the_company_column")   # corrupt file NOT clobbered


def test_write_research_is_write_once(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    src.write_research(pd.DataFrame([{"company": "NewCo", "funding_finding": "first"}]))
    src.write_research(pd.DataFrame([{"company": "NewCo", "funding_finding": "second"},
                                     {"company": "Other Co", "funding_finding": "c"}]))
    _, research_df = src.read_review_data()
    companies = list(research_df["company"])
    assert companies.count("NewCo") == 1 and "Other Co" in companies   # existing kept, new appended
    assert research_df[research_df["company"] == "NewCo"].iloc[0]["funding_finding"] == "first"


def test_run_batch_persists_status_readable_after(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Brand New A"])
    research.run_batch(src, work_dir=tmp_path / "jobs",
                       research_and_score=_stub_research_and_score([]), clock=CLOCK)
    persisted = research.read_status(tmp_path / "jobs")
    assert persisted["state"] == "done" and persisted["finished_at"]
    assert not research.is_running(tmp_path / "jobs")


def test_run_batch_no_new_candidates_is_done_immediately(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["alpha health"])                                      # already in the ledger
    seen = []
    status = research.run_batch(src, work_dir=tmp_path / "jobs",
                                research_and_score=_stub_research_and_score(seen), clock=CLOCK)
    assert status["state"] == "done" and status["total"] == 0 and seen == []


def test_failure_reason_is_recorded_in_status(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Good Co", "Bad Co"])

    def _rs(companies, on_progress):
        on_progress("Bad Co", "failed", "APIError: internal_server_error")
        on_progress("Good Co", "completed")
        return [_rec("Good Co")], pd.DataFrame([{"company": "Good Co", "funding_finding": "Seed"}])

    status = research.run_batch(src, work_dir=tmp_path / "jobs", research_and_score=_rs, clock=CLOCK)
    assert status["state"] == "done" and status["failed"] == 1 and status["added"] == 1
    assert status["failures"] == [{"company": "Bad Co", "reason": "APIError: internal_server_error"}]


def test_run_batch_records_failure_and_leaves_ledger_untouched(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    before = [e["company"] for e in src.read_entries()]
    _seed(src, ["Brand New A"])

    def _boom(companies, on_progress):
        raise RuntimeError("openai exploded")

    status = research.run_batch(src, work_dir=tmp_path / "jobs", research_and_score=_boom, clock=CLOCK)
    assert status["state"] == "failed" and "openai exploded" in status["error"]
    assert [e["company"] for e in src.read_entries()] == before       # nothing written on failure


def test_run_batch_all_failed_roster_is_a_failure(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Brand New A"])

    def _empty(companies, on_progress):
        on_progress(companies[0], "failed")
        return [], pd.DataFrame()

    status = research.run_batch(src, work_dir=tmp_path / "jobs", research_and_score=_empty, clock=CLOCK)
    assert status["state"] == "failed" and "nothing to score" in status["error"]


# --- background launch + startup auto-resume ---------------------------------

def test_start_run_completes_in_background(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Brand New A"])
    jobs, seen = tmp_path / "jobs", []
    thread = research.start_run(src, work_dir=jobs, client_factory=lambda: None,
                                research_and_score=_stub_research_and_score(seen))
    assert thread is not None
    thread.join(timeout=10)
    assert research.read_status(jobs)["state"] == "done" and seen == ["Brand New A"]


def test_start_run_blocked_when_already_running(tmp_path):
    jobs = tmp_path / "jobs"
    research._write_status(jobs, {"state": "running", "batch_id": "x"})   # a run is active
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    thread = research.start_run(src, work_dir=jobs, client_factory=lambda: None,
                                research_and_score=_stub_research_and_score([]))
    assert thread is None                                                 # one run at a time


def test_resume_if_running_relaunches_interrupted_batch(tmp_path):
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    _seed(src, ["Brand New A"])
    jobs = tmp_path / "jobs"
    research._write_status(jobs, {"state": "running", "batch_id": "batch_interrupted", "total": 1,
                                  "completed": 0, "reused": 0, "failed": 0, "added": 0,
                                  "current_company": "", "error": "", "started_at": "", "finished_at": ""})
    thread = research.resume_if_running(src, work_dir=jobs, client_factory=lambda: None,
                                        research_and_score=_stub_research_and_score([]))
    assert thread is not None
    thread.join(timeout=10)
    assert research.read_status(jobs)["state"] == "done"


def test_resume_is_noop_when_not_running(tmp_path):
    jobs = tmp_path / "jobs"
    research._write_status(jobs, {"state": "done"})
    src = FixtureDashboardSource(FIXTURE, review_work_dir=tmp_path / "store")
    assert research.resume_if_running(src, work_dir=jobs, client_factory=lambda: None) is None
