"""Phase-3 hosted research runner — orchestrator + durable job status.

Composes the tested engine — `research_runner.run_research_batch` (research + per-company checkpoint/resume) →
`research_runner.run_r1` (deterministic §B scoring roster) → `ledger.build_gate2_artifacts` (transactional batch
ledger) — and MERGES the scored entries into the store's `ledger.jsonl` (write-once; existing entries/overrides
are never overwritten). A small JSON job-status on the persistent disk drives the progress page and lets a restart
auto-resume from the checkpoint.

Rule 4/5: per-company checkpoint resume + the batch is only "done" after the merged ledger is reopened and the new
companies confirmed present. Rule 6/8: deterministic write-once scores; existing entries preserved. Rule 7: this is
orchestration of the deterministic tools — no research/scoring prompt changes.

Offline-testable: the client-driven research/score step is injectable (`research_and_score`), so tests exercise the
wiring (status, dedup, ledger build, merge, read-back, failure) with no OpenAI client.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .. import ledger, research_runner
from .. import structured_evidence as se
from ..storage import load_csv

logger = logging.getLogger(__name__)

DEFAULT_MODEL = research_runner.DEFAULT_MODEL
_STATUS_FILE = "job_status.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(name: Any) -> str:
    return str("" if name is None else name).strip().lower()


# --- durable job-status store (one JSON on the persistent disk; one run at a time) -------------------------

def status_path(work_dir) -> Path:
    return Path(work_dir) / _STATUS_FILE


def read_status(work_dir) -> dict | None:
    path = status_path(work_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _write_status(work_dir, status: dict) -> None:
    path = status_path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(status), encoding="utf-8")
    tmp.replace(path)   # atomic swap — a crash mid-write never leaves a torn status file


def is_running(work_dir) -> bool:
    status = read_status(work_dir)
    return bool(status) and status.get("state") == "running"


# --- the default (real) research + score step; injected with a fake in offline tests ----------------------

def _default_research_and_score(*, client, model, taxonomy_dir, checkpoint_path,
                                wait_between_searches, wait_between_passes, sleep_fn) -> Callable:
    def _run(companies, on_progress):
        research_runner.run_research_batch(
            companies, client=client, checkpoint_path=checkpoint_path, model=model, taxonomy_dir=taxonomy_dir,
            wait_between_searches=wait_between_searches, wait_between_passes=wait_between_passes,
            sleep_fn=sleep_fn, on_progress=on_progress)
        df = load_csv(checkpoint_path)
        report = research_runner.run_r1(df, client=client, model=model)
        return report["roster"], df
    return _run


def run_batch(source, *, work_dir, client=None, batch_id: str | None = None, model: str = DEFAULT_MODEL,
              taxonomy_dir=None, research_and_score: Callable | None = None,
              wait_between_searches: float = research_runner.DEFAULT_WAIT_BETWEEN_SEARCHES,
              wait_between_passes: float = research_runner.DEFAULT_WAIT_BETWEEN_PASSES,
              sleep_fn=time.sleep, clock=_now) -> dict:
    """Research + score every not-yet-researched approved candidate; merge the scored entries into the store's
    ledger (write-once); record durable progress throughout. Returns the final status dict."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    batch_id = batch_id or clock().strftime("batch_%Y%m%d_%H%M%S")

    existing = source.read_entries()
    have = {_norm(e.get("company")) for e in existing}
    companies = [c for c in source.read_candidates() if _norm(c) and _norm(c) not in have]

    status = {"batch_id": batch_id, "state": "running", "total": len(companies), "completed": 0,
              "reused": 0, "failed": 0, "added": 0, "current_company": "", "error": "",
              "started_at": clock().isoformat(), "finished_at": ""}
    _write_status(work_dir, status)

    if not companies:   # nothing new to research (all candidates already in the ledger)
        status.update(state="done", finished_at=clock().isoformat())
        _write_status(work_dir, status)
        return status

    def on_progress(company, kind):
        current = read_status(work_dir) or status
        if kind in ("completed", "reused", "failed"):
            current[kind] = current.get(kind, 0) + 1
        current["current_company"] = str(company)
        _write_status(work_dir, current)

    def _fail(message) -> dict:
        current = read_status(work_dir) or status
        current.update(state="failed", error=str(message), finished_at=clock().isoformat())
        _write_status(work_dir, current)
        return current

    if research_and_score is None:
        research_and_score = _default_research_and_score(
            client=client, model=model, taxonomy_dir=taxonomy_dir,
            checkpoint_path=work_dir / f"{batch_id}_checkpoint.csv",
            wait_between_searches=wait_between_searches, wait_between_passes=wait_between_passes, sleep_fn=sleep_fn)

    try:
        roster, research_df = research_and_score(companies, on_progress)
    except Exception as exc:   # noqa: BLE001 — a run failure is recorded, never crashes the server
        return _fail(f"{type(exc).__name__}: {exc}")

    if not roster:
        return _fail("No companies were researched successfully (all failed) — nothing to score.")

    artifacts = ledger.build_gate2_artifacts(
        roster, research_df, batch_id=batch_id, date_scored=clock().date().isoformat(),
        out_dir=work_dir / batch_id, framework_version=se.FRAMEWORK_VERSION)
    if not artifacts.readback_ok:
        return _fail("Batch ledger failed read-back validation (Rule 5).")

    # Merge write-once: only companies not already in the ledger are added; existing entries/overrides untouched.
    new_entries = ledger.read_ledger(artifacts.ledger_path)
    to_add = [e for e in new_entries if _norm(e.get("company")) not in have]
    if not source.write_entries(existing + to_add):
        return _fail("Ledger merge failed read-back validation — results NOT saved.")

    after = {_norm(e.get("company")) for e in source.read_entries()}   # Rule 5: reopen + confirm
    missing = [e.get("company") for e in to_add if _norm(e.get("company")) not in after]
    if missing:
        return _fail(f"Merged ledger missing companies after read-back: {missing}")

    final = read_status(work_dir) or status
    final.update(state="done", current_company="", added=len(to_add), finished_at=clock().isoformat())
    _write_status(work_dir, final)
    return final


# --- background launch + startup auto-resume (the in-process job model) ------------------------------------

def _spawn(source, *, work_dir, client_factory, taxonomy_dir, batch_id, research_and_score,
           on_finish) -> threading.Thread:
    def _target():
        try:
            status = run_batch(source, work_dir=work_dir, client=client_factory(), taxonomy_dir=taxonomy_dir,
                               batch_id=batch_id, research_and_score=research_and_score)
        except Exception as exc:   # noqa: BLE001 — guard client_factory()/thread; run_batch records its own failures
            logger.exception("research batch thread crashed")
            status = read_status(work_dir) or {}
            status.update(state="failed", error=f"runner thread crashed: {exc}", finished_at=_now().isoformat())
            _write_status(work_dir, status)
        if on_finish is not None:
            try:
                on_finish(status)
            except Exception:   # noqa: BLE001 — a notification failure must not crash the worker
                logger.exception("research on_finish hook failed")

    thread = threading.Thread(target=_target, name="htra-research", daemon=True)
    thread.start()
    return thread


def start_run(source, *, work_dir, client_factory, taxonomy_dir=None, research_and_score=None,
              on_finish=None) -> threading.Thread | None:
    """Start a research run in a background thread. Returns the thread, or None if a run is already active
    (one run at a time). `research_and_score` is a test seam (defaults to the real engine)."""
    if is_running(work_dir):
        return None
    return _spawn(source, work_dir=work_dir, client_factory=client_factory, taxonomy_dir=taxonomy_dir,
                  batch_id=None, research_and_score=research_and_score, on_finish=on_finish)


def resume_if_running(source, *, work_dir, client_factory, taxonomy_dir=None, research_and_score=None,
                      on_finish=None) -> threading.Thread | None:
    """On process startup: if the durable status says a run was mid-flight, relaunch it with the SAME batch_id so
    `run_research_batch` resumes from the checkpoint (completed companies are reused, not re-researched)."""
    status = read_status(work_dir)
    if not status or status.get("state") != "running":
        return None
    logger.info("Resuming interrupted research batch %s", status.get("batch_id"))
    return _spawn(source, work_dir=work_dir, client_factory=client_factory, taxonomy_dir=taxonomy_dir,
                  batch_id=status.get("batch_id"), research_and_score=research_and_score, on_finish=on_finish)


# --- the /research progress page (static shell; the JS polls /research/status) -----------------------------

_RESEARCH_CSS = """
.rwrap{max-width:640px;margin:0 auto}
.rtop{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}
.rcard{background:var(--surface-2);border:1px solid var(--border);border-radius:14px;padding:20px 22px;box-shadow:var(--shadow)}
.rstate{font-size:15px;font-weight:800;margin-bottom:12px}
.rstate.run{color:var(--accent-ink)}.rstate.done{color:#1E7A3E}.rstate.fail{color:#791F1F}
.rbar{height:12px;background:var(--surface-1);border:1px solid var(--border);border-radius:20px;overflow:hidden;margin:12px 0}
.rfill{height:100%;background:var(--accent);transition:width .4s ease}
.rline{font-size:13px;color:var(--text-primary);margin-top:8px}
.rcounts{font-size:12px;color:var(--text-secondary);margin-top:12px}
.rerr{font-size:12.5px;color:#791F1F;margin-top:8px;word-break:break-word}
.rmuted{font-size:13px;color:var(--text-secondary);line-height:1.5}
.rbtn{display:inline-block;margin-top:14px;font-size:13px;font-weight:600;background:var(--navy);color:#fff;border:1px solid var(--navy);border-radius:9px;padding:9px 15px;text-decoration:none}
.rbtns{font:inherit;font-size:12.5px;font-weight:600;background:var(--surface-2);border:1px solid var(--border-strong);border-radius:8px;padding:7px 13px;color:var(--navy);text-decoration:none}
"""

_RESEARCH_JS = r"""
(function(){
  var box=document.getElementById('rstat');
  function esc(v){var d=document.createElement('div');d.textContent=(v==null?'':v);return d.innerHTML;}
  function pct(s){return s.total?Math.round(100*((s.completed||0)+(s.reused||0))/s.total):0;}
  function bar(s){return '<div class="rbar"><div class="rfill" style="width:'+pct(s)+'%"></div></div>';}
  function counts(s){return '<div class="rcounts">'+esc(s.completed||0)+' researched · '+esc(s.reused||0)+' reused · '+esc(s.failed||0)+' failed · of '+esc(s.total||0)+'</div>';}
  function render(s){
    if(!s||!s.state){box.innerHTML='<div class="rmuted">No research run yet. Approve a candidate list at GATE-1 to start one — it runs here automatically.</div>';return;}
    var h='';
    if(s.state==='running'){h+='<div class="rstate run">Researching…</div>'+bar(s)+'<div class="rline">Current: <b>'+esc(s.current_company||'starting…')+'</b></div>';}
    else if(s.state==='done'){h+='<div class="rstate done">Done ✓</div>'+bar(s)+'<div class="rline">Added <b>'+esc(s.added||0)+'</b> newly-scored companies to your ledger.</div><a class="rbtn" href="/review">Review them at GATE-2 →</a>';}
    else if(s.state==='failed'){h+='<div class="rstate fail">Run failed</div>'+bar(s)+'<div class="rerr">'+esc(s.error||'')+'</div><div class="rline">Completed companies are saved; starting a new run re-attempts only what didn’t finish.</div>';}
    box.innerHTML=h+counts(s);
  }
  var timer;
  function poll(){fetch('/research/status').then(function(r){return r.json();}).then(function(s){render(s);if(s&&(s.state==='done'||s.state==='failed')){clearInterval(timer);}}).catch(function(){});}
  poll();timer=setInterval(poll,3000);
})();
"""


def render_page() -> str:
    from .. import dashboard_html
    body = ('<div class="rwrap"><div class="rtop">'
            '<div class="apptitle" style="color:var(--navy)">Research run</div>'
            '<div><a class="rbtns" href="/">&larr; Dashboard</a></div></div>'
            '<div class="rcard"><div id="rstat"><div class="rmuted">Loading…</div></div></div></div>')
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Research run</title>'
            f'<style>{dashboard_html._CSS}{_RESEARCH_CSS}</style></head><body><div class="wrap">{body}</div>'
            f'<script>{_RESEARCH_JS}</script></body></html>')
