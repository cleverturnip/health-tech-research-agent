# Front-end Phase 3 — the hosted research/scoring runner (BUILD SPEC)

Status/roadmap lives in `COLLABORATION_CONTEXT.md` § Status & roadmap. This is the design contract for the
research runner — the segment that turns an approved GATE-1 candidate list into scored `ledger.jsonl` entries,
**server-side**, replacing the hand-run Colab cells. Decisions below were made with Katelynd 2026-07-05.

## 1. What it delivers

The autonomous segment BETWEEN the gates: GATE-1 approval → **research + deterministic scoring of each approved
company** → new entries land in the durable `ledger.jsonl` → they appear in the already-built **GATE-2 review**
and dashboard. Runs entirely on the host (no Colab), survives idle periods and restarts, shows live progress, and
emails Katelynd on completion or failure.

Per the locked architecture (CLAUDE.md): between GATE-1 and GATE-2 there is **zero user input** — approving the
candidate list is the trigger; the segment runs autonomously and surfaces its result at GATE-2.

## 2. Locked decisions (2026-07-05, with Katelynd)

1. **Execution model:** Render **Starter** plan (always-on; the free plan sleeps when idle and would kill a run).
   Research runs as an **in-process background job** in the existing web service — one service, one bill, reusing
   the existing checkpoint/manifest resume logic. (Not a separate worker; not Colab.)
2. **Durability:** the in-flight **checkpoint + manifest + job-status** live on a **Render persistent disk** so a
   restart mid-run resumes from the last completed company. (A few cents/month.)
3. **Results → ledger:** completed research is scored deterministically and **merged into the Drive `ledger.jsonl`**
   as new write-once, un-finalized entries — so the built GATE-2 review + dashboard pick them up with no new UI.
4. **Notification:** **email** on finish/failure (Resend free tier; one `RESEND_API_KEY` Render secret) to
   Katelynd's address, plus a live in-app progress page.
5. **Trigger:** **auto-start on GATE-1 approval** — approving the candidate list kicks off the run and lands on the
   progress page.

**Cost on the table:** Render Starter ~$7/mo + a small persistent disk (cents) + Resend free tier + OpenAI usage
per run (unchanged from today's Colab runs).

## 3. Flow (end to end)

1. **GATE-1 approve** (`POST /discover/approve`, already built) appends the approved rows to `candidates.csv` in
   Drive, then **enqueues a research batch** and redirects to `/research`.
2. **Orchestrator** (new, background thread):
   a. Read `candidates.csv` from Drive; take the companies **not already researched** in `ledger.jsonl` (dedup —
      belt-and-suspenders on top of the GATE-1 exclude filter).
   b. `research_runner.run_research_batch(companies, client=…, checkpoint_path=<disk>/<batch>_checkpoint.csv, …)`
      — per-company research with atomic checkpointing + resume (existing, tested).
   c. Score each completed checkpoint row: `structured_evidence.score_checkpoint_row` → a scored roster (Rule 7,
      deterministic; scores are write-once — never hand-edited, Rule 8).
   d. `ledger.build_gate2_artifacts(roster, research_df, batch_id, date_scored, out_dir)` → a batch `ledger.jsonl`
      (transactional: backup + read-back + rollback, Rules 4/5).
   e. **Merge** the batch entries into the Drive `ledger.jsonl` (read existing → append the new companies
      write-once → `write_file_to_folder` update + read-back). Existing entries are never overwritten (Rule 6/8).
   f. Update the durable **job-status** after each company (progress) and on finish/failure.
3. **`/research` progress page** polls the job-status: "company X of N · <current> · elapsed", plus reused/failed
   counts. On finish it links to GATE-2 review; on failure it shows what failed (failed companies auto-retry on
   the next run — they were never checkpointed).
4. **Email** on finish/failure with a link back to `/research` (or `/review`).
5. From here the **existing** GATE-2 review handles the human decision; nothing new downstream.

## 4. Job lifecycle, durability & resume (Rule 4)

- **Job-status store:** a small JSON on the persistent disk — `{batch_id, state: queued|running|done|failed,
  total, completed, reused, failed, current_company, started_at, finished_at, error}`. Written after each company.
- **One run at a time:** a new enqueue is rejected (409) while a batch is `running` — this is a personal,
  single-run tool; no concurrency.
- **Restart mid-run:** on app startup, if a batch is `running` (state on disk) but no thread is alive, the app
  **auto-relaunches** the background job; `run_research_batch` resumes from the checkpoint (completed companies are
  `reused`, not re-researched). A runtime loss thus repeats no completed work.
- **Read-back before "done":** the batch is only marked `done` after the merged Drive `ledger.jsonl` is reopened
  and the new companies are confirmed present (Rule 5).

## 5. Reused vs new

**Reused (unchanged):** `research_runner.run_research_batch` + all its search/recovery/fit-brief functions;
`structured_evidence.score_checkpoint_row`; `ledger.build_gate2_artifacts` / `execute_ledger_write` /
`read_ledger`; the GATE-2 review UI; the dashboard; `gsource` Drive read/update helpers.

**New:** `webapp/research.py` (orchestrator + job-status store + Drive ledger-merge), background-thread execution
+ startup auto-resume in `app.py`/`asgi.py`, the `/research` progress page (+ polling JSON route), a small
`webapp/email.py` (Resend), and the Render config (Starter + disk + secret).

## 6. Rules honored

- **Rule 4/5** — durable, validated, resumable; "done" only after ledger read-back.
- **Rule 6/8** — deterministic scoring; scores write-once; existing entries/overrides never overwritten by a run.
- **Rule 7** — the runner orchestrates the deterministic research+scoring tools; the LLM gathers/interprets
  evidence inside the (unchanged) research prompts; priority is the deterministic model; humans decide at the gates.
- **Prompts unchanged** — this is orchestration only; no research/scoring prompt wording changes (highest-stakes;
  would be a separate, signed-off change).

## 7. Out of scope (later)

- Concurrency / multiple simultaneous runs.
- The one-fact re-research / paste-a-correction path (a separate pipeline item — carry-forward; doc-first).
- Auto-advancing GATE-2 (the human decision stays; the runner stops at the review gate).

## 8. Build order (each slice tested before the next)

1. **This spec** (done — for review).
2. **Orchestrator + job-status store** (`webapp/research.py`), offline with a fake client + a fixture source:
   candidates → research → score → batch ledger → Drive-merge; unit-tested (resume, dedup, read-back, failure).
3. **Background execution + startup auto-resume** in the app; `/research` page + polling route; TestClient tests.
4. **Email** (`webapp/email.py`, Resend) — injected/faked offline; a finish + a failure email path, tested.
5. **Render config** (Starter + persistent disk + `RESEND_API_KEY`) in `render.yaml`; then a **live 1–2 company
   test batch** end-to-end before any real run.
