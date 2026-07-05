# Collaboration Context — Health-Tech Research Agent

> **How to use this file:** Starting a NEW chat with Claude, upload or paste this file's full contents
> and say: *"I'm continuing a project — read this context doc and confirm you understand where we are
> before we continue."* Whether a browser Claude chat can read my repo on its own depends on that chat's
> tools: the repo is **public**, so a chat with web-search / fetch enabled CAN pull individual files, but
> a plain chat without browsing tools can't — and even when it can, pasting this file is the reliable,
> complete handoff (no partial or stale fetches). Claude Code has direct repo access.

## Who I am / how we work
I'm Katelynd (GitHub: cleverturnip), a non-coder building a health-tech company
research-and-prioritization agent. Repo: github.com/cleverturnip/health-tech-research-agent

Working model: **design and strategize with Claude in chat; hand finished specs/prompts to
Claude Code** (which has live repo access) to execute. I run live research in a **Colab notebook**
and keep data in Google Drive. Keep this division: Claude helps me think, design, and review;
Claude Code builds.

## North Star — the end-state flow (every decision moves toward this)
A research agent that runs as a mostly-autonomous flow bounded by exactly TWO human-in-the-loop gates:

1. User defines the parameters for the kinds of companies to research → the LLM offers candidate
   suggestions → **[GATE 1]** user approves/edits the candidates.
2. From that approval, a FULLY AUTONOMOUS segment runs with NO user input: it researches the
   approved companies and writes a raw-research batch CSV; scores that research into a **scoring
   ledger** (the §B model); reviews its own output; and produces **review cards + a short summary
   table** with a recommendation attached → **[GATE 2]** user reviews and edits/approves. (The
   review surface is CSV.)
3. From that approval, a second FULLY AUTONOMOUS segment runs with NO user input: it outputs the
   **dashboard**.

**The load-bearing design fact: between GATE 1 and GATE 2, and between GATE 2 and the dashboard,
there is ZERO user input.** Those segments must be architected to run unattended end-to-end — a
problem inside a segment cannot rely on a human noticing it mid-flow. It must be handled
autonomously or surfaced AT THE NEXT GATE for review. When architecting any change inside an
autonomous segment, design for "no one is watching this run" — the flag-for-review pattern (e.g.
`capability_needs_review` routing a row to human attention) is how an autonomous segment defers a
judgment to a gate instead of stalling or guessing.

## How we work — disciplines
> Claude Code's binding working rules are canonical in **`CLAUDE.md`** (Architecture rules + "How I
> want you to work"). This is the design-chat summary of the ones that shape design:

- Investigate (read-only) → plan (no code) → implement red→green, in small reviewable commits.
- Never weaken a validation gate to make something pass.
- Capture every decision durably in the repo (specs / status / runbook) — nothing important lives
  only in chat.
- The single full data regeneration is **run-once** — everything must be right before it.
- Prompt wording for any LLM-facing change is the highest-stakes review — design it together before
  Claude Code builds it.
- **Intent-to-action:** when a recorded intent isn't directly, unambiguously actionable, STOP and
  confirm the exact translation before building — the plausible-but-wrong reading is the recurring
  failure mode (it reads reasonably and only a live run exposes it).
- **Rule 7** — the LLM gathers EVIDENCE; deterministic rules DECIDE. Persist evidence as columns so
  labels/signals are recomputable without re-research.
- **Rule 9 — absence is an upper bound, not a measurement:** a blank / "not found" in our OWN output
  means the data isn't IN our output — it does NOT establish the data doesn't exist. Never attribute
  a cause to an empty field from output alone; convert the bound to a measurement with a live test
  (e.g. a repeat-N variance probe) before building on it.
- Every temporary measure is built toward the North Star end state — solve the immediate step in the
  shape the end state will reuse, not a throwaway shape.
- The scoring + priority framework has ONE source of truth
  (`specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`, FRAMEWORK_VERSION-stamped): scoring changes edit the
  DOC FIRST (version bumps), committed BEFORE anything that depends on it. Output cites the framework
  version it was built against, so staleness is visible.

## Source-of-truth files (current)
1. `specs/COLLABORATION_CONTEXT.md` — this file: flow, how-we-work, and current status/roadmap.
2. `specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` — the §B scoring + priority framework (locked, v1.25).
3. `specs/MASTER_REDESIGN_SPEC.md` — the scoring-ledger + cards + summary-table design (BUILT 2026-07-03;
   §4 is the render contract; visual ref `specs/gate2_review_surface_mockup.html`). The ledger IS
   `src/health_tech_research_agent/ledger.py` (durable `ledger.jsonl` + three CSV views).
4. `specs/DASHBOARD_DESIGN.md` — the dashboard segment design + build + Colab run steps (BUILT + live-verified
   2026-07-03; visual ref `specs/dashboard_wireframe.html`). The dashboard IS
   `src/health_tech_research_agent/dashboard.py` (+ `dashboard_html.py` / `dashboard_gsheet.py`).
5. `specs/FRONT_END_DIRECTION.md` — the full-flow front-end DIRECTION (decided 2026-07-03): what we're building
   (hosted, private, desktop-first app for the two-gate flow) + the phase order. The current-milestone contract.
6. `specs/FRONT_END_PHASE1_HOSTED_DASHBOARD.md` — the Phase-1 (hosted dashboard) BUILD SPEC + deploy runbook
   (FastAPI + Render, password login, least-privilege Google, on-the-spot Refresh, in-app pursue).
7. `specs/FRONT_END_PHASE2_GATE2_REVIEW.md` — the Phase-2 (in-app GATE-2 review) BUILD SPEC: the review card =
   the dashboard detail card + a priority decision control; decisions write the ledger back to Drive.
8. `specs/SCORING_WALKTHROUGH.md` — plain end-to-end walkthrough of how a company gets scored.
9. `specs/regen_execution_runsheet.md` + `specs/phase2_refresh_runbook.md` — regeneration runbooks (active).
10. `CLAUDE.md` — Claude Code's working rules and repo map.

Superseded/historical material (finished slices, the old `candidate_priority` engine, Phase-3 process
history, audits, one-off probes) lives in `archive/` — reference only.

## Status & roadmap (single source of truth for where we are)

**🎉 FRONT END COMPLETE — validated end-to-end on the live site (2026-07-06).** One uninterrupted pass on the hosted
app: GATE-1 discovery → approve → **autonomous research on the live server** → GATE-2 review with complete cards
(research + evidence joined) → finalize → dashboard → pursue. Proved the fixes in flight: Clair Health completed (the
fit-brief retry beat the JSON truncation bug), Suno completed, both research rows persisted to `research.csv` and
linked correctly on the cards. Katelynd reviewed/adjusted priorities, companies flowed to the dashboard, Clair moved to
Pursue. Ledger now 56 companies, all reviewed. Research writes are guarded (append-only, write-once, abort-on-suspect,
grow-only — completed research can't be clobbered by a new run; proven on the real 54-row file). **Definition of done
met.** (Minor calibration note below re: non-health segment routing.)

**Done & locked:**
- **Research-prompt overhaul** — the search layer gathers enough quantity/quality/breadth to score
  off of; wording-locked and tested.
- **Data repopulated (regen 2)** — the main company list re-researched on the hardened pipeline; the
  research CSV holds the current raw data.
- **Scoring-model overhaul (§B)** — the gated-then-ranked scoring + priority framework, locked at
  FRAMEWORK v1.25 in Phase 3 and merged. Rules: `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`; why-history:
  `archive/specs/PHASE3_PROCESS_HISTORY.md`.
- **GATE-2 scoring ledger + review packet (2026-07-03)** — the durable `ledger.jsonl` master + the three
  rendered CSV views (summary / cards / master export), per `MASTER_REDESIGN_SPEC.md` §4. Built as
  importable package functions (`ledger.py` + `research_runner` orchestration): uniform scoring (every
  company scored — floors cap PRIORITY, not scoring), write-once §B scores, the priority-only decision
  round-trip (`cards.csv` → `apply_decisions` → history, Rule 6/8), research evidence joined at render, and
  the full review-and-decide card. 597 tests + **live-verified on a Colab run**. Both design requirements
  met: floored-vs-low legibility (B2B → `n/a`; distinct from a low score) and the walkthrough doc
  (`SCORING_WALKTHROUGH.md`). Render design locked in `MASTER_REDESIGN_SPEC.md` §4 + `gate2_review_surface_mockup.html`.

- **Dashboard segment (2026-07-03) — BUILT + LIVE-VERIFIED, merged to `main`.** The second autonomous segment:
  reads the GATE-2-reviewed ledger and builds Katelynd's career-search working tracker. New ledger-based
  `dashboard.py` (the old one deleted): the per-company data model + grid projections (all companies · pursuit ·
  contacts · segment radar) + the per-company detail view (scoring + 3-layer research evidence), the §1a review
  stamp (`ledger.finalize_gate2_review*`), the living-layer merge (your notes preserved, "changed"/"orphaned"
  safety signals), an HTML render, and the `build_dashboard` orchestrator. Editable store is a **native Google
  Sheet** (input-only via `gspread` — the build never overwrites your edits). Design: `specs/DASHBOARD_DESIGN.md`
  (+ `dashboard_wireframe.html`); ~40 tests; live-verified on the regen-2 Colab run (54 companies).

**Current milestone (IN PROGRESS): the FRONT END** + the data system that houses the flow so it runs autonomously
end-to-end instead of through Colab cells. **Direction DECIDED with Katelynd 2026-07-03 — see
`specs/FRONT_END_DIRECTION.md`:** a hosted, private (login), desktop-first web app for the full two-gate flow
(GATE 1 conversational + ledger-grounded discovery → autonomous long research run with progress + notification →
in-app GATE 2 review → hosted dashboard with a Google-Sheet input layer + Refresh). Phase order: **① hosted
dashboard first** → ② in-app GATE 2 → ③ GATE 1 + the long-run orchestration (replaces Colab as the engine, done
last). The dashboard engine already emits the durable data artifact the front end will render (the HTML render +
Google-Sheet store are the interim surface; the front end swaps the surface, reusing the engine unchanged — see
`DASHBOARD_DESIGN.md` §7). Contract: `specs/FRONT_END_PHASE1_HOSTED_DASHBOARD.md`.

**Phase 1 — hosted dashboard: BUILT + DEPLOYED + LIVE on Render (2026-07-04).** The FastAPI web
shell (`src/health_tech_research_agent/webapp/`) over the existing dashboard engine (Rule 1): simple-password
login + session gate; on-the-spot Refresh (rebuilds from Google, visible overlay, keeps your tab); a Google-backed
source that reads `ledger.jsonl` + the research CSV from a shared Drive folder + the dashboard Sheet via a
least-privilege service account; **in-app `pursue` editing** writes one cell back to the Sheet (read-back verified;
narrowly widened the Sheet scope to write — spec §8a). Polished analytics UI (navy/blue-ramp/cyan/gold reference
palette, KPI tiles, dark table headers + zebra, segment-radar chart, colored company-detail view). Verified end-to-end
against Katelynd's real Google data (54 companies); 669 tests. Also fixed a dup-column bug (reference columns leaking
into the user layer). **DEPLOYED to Render** (Blueprint `render.yaml`, editable install; **free** plan; login-password
hash + Drive folder id as env vars; the service-account key as a Render **Secret File** — pasting it into an env var
mangled the JSON, so `credentials_info` prefers the mounted file at `/etc/secrets/service_account.json`). The free
tier **sleeps when idle** (~1 min cold start) — upgrade to `starter` for always-on (needed before the Phase-3 long
jobs). The exposed-key from setup was **rotated** (2026-07-04) and the old key deleted.

**Phase 2 — in-app GATE-2 review: BUILT + merged + DEPLOYED (2026-07-04).** `specs/FRONT_END_PHASE2_GATE2_REVIEW.md`.
Review pending (researched+scored, un-finalized) companies as full cards in the app and decide priority (Accept the
model tier / Override + reason), then Finalize → they flow to the dashboard (replaces editing `cards.csv`). The review
card = the dashboard **detail card body** (`dashboard_html._detail_body`, shared) + a priority decision control
(select-then-Save; a "why this recommendation" write-up from `recommended_action` + flags + floor — §2a; no dedicated
LLM field exists). List: sorted by final score, whole-row clickable, green when decided (`decision.decided_date`).
Decisions apply priority-only + history (Rule 6/8) and **write the ledger back to the Drive data folder** (targeted
`files.update`, read-back verified — Rule 4/5; folder scope widened Viewer→**Editor**, spec §4); Finalize stamps §1a.
Reuses `ledger.apply_decisions`/`finalize_gate2_review`. 23 tests (suite 688). Nothing pending on the live ledger yet
(all finalized) — exercised on the next real batch.

**Phase 3 — GATE-1 in-app discovery: BUILT on branch `frontend-phase3-gate1`, pending deploy (2026-07-04).**
`specs/FRONT_END_PHASE3_GATE1_DISCOVERY.md`. A `/discover` page: a saveable **thesis** (her target-market baseline,
stored `thesis.md` in the Drive folder), a **conversational, ledger-grounded** chat (OpenAI + **web search**), and an
**approve** step that writes `candidates_<date>.csv` to Drive for the research run. The LLM is grounded every turn on
the LOCKED discovery prompt (spec §2a) filled with: her thesis + the full compact **scored roster** + her **manual
priority overrides (with reasons)** + a **do-not-repeat exclude list** of everything researched (raw research write-ups
deliberately excluded — too large). Rule 7: the LLM only *proposes*; she approves at GATE-1 and the deterministic §B
scoring happens downstream in research. Web-verified real companies collect in a tray (drop any before approving);
approve appends to the CSV read-back-verified (Rule 4/5). OpenAI failure surfaces a retryable error, never crashes the
chat. 28 tests (suite 707). **Live-verify (2026-07-05)** against her real ledger + real OpenAI key confirmed the call,
web search, grounding (54 companies + 5 overrides), and parsing all work — and surfaced two findings: (a) the model
re-proposed already-researched companies despite the exclude list → fixed with a **deterministic dedup filter**
(`gate1.drop_researched`, Rule 7; name-normalized so "Levels"↔"levels health"); (b) the **service account can't CREATE
Drive files** (free-Gmail quota) → thesis + candidates are now **pre-created Katelynd-owned files the app only UPDATES**
(`thesis.md`; append-only `candidates.csv` with a `date` column — replaces the dated-file plan). See
`sa-cannot-create-drive-files`. **Final live-verify passed (2026-07-05):** real thesis grounds from Drive, thesis
update + candidates append round-trip read-back-verified (test row restored clean), dedup correct on real output
(dropped 0 of 8 legit new). 710 tests. **MERGED to main + DEPLOYED + CONFIRMED LIVE on Render (2026-07-05):**
`/discover` is live + login-gated; the logged-in chat works end-to-end (thesis pre-fills from Drive → live OpenAI +
web-search call → candidates → dedup). Two deploy-only fixes surfaced AFTER first deploy and were shipped: (a) `openai`
was only in the `research` extra but Render installs `.[web]` → moved `openai` into the **`web` extra** (server-side
call was failing with "Could not reach the assistant"); (b) dedup missed a multi-word re-proposal ("Oura Ring" for
stored "oura") → switched to **core-token subset matching** (drops generic words incl. "ring"), validated on the real
54-company ledger (drops researched variants, zero over-drops). **GATE-1 is fully live.**

**Phase 3 — hosted research/scoring runner: BUILT on branch `frontend-phase3-research-runner`, pending Render ops +
live test (2026-07-05).** `specs/FRONT_END_PHASE3_RESEARCH_RUNNER.md`. Replaces the hand-run Colab research: GATE-1
approve **auto-starts** a background run → `research_runner.run_research_batch` (per-company research + resumable
checkpoint) → `run_r1` (deterministic §B scoring roster) → `ledger.build_gate2_artifacts` → **merged write-once into
the Drive `ledger.jsonl`** (existing entries/overrides untouched; read-back before "done") → appears in GATE-2 review +
dashboard. A durable JSON job-status on a **Render persistent disk** drives the `/research` progress page (polled) and
lets a restart **auto-resume from the checkpoint** (same batch_id; Rule 4). Email on finish/failure via **Resend**
(`webapp/email.py`). One run at a time. `webapp/research.py` + `webapp/email.py`; `run_research_batch` gained an
additive `on_progress` hook. Offline-tested (client-driven step injected). **LIVE-VERIFIED end-to-end 2026-07-05** (real OpenAI key, real Drive
ledger, 2-company batch Clair Health + Sandbar): Sandbar researched → scored → **merged into the real ledger** (55, the
54 existing preserved), **email delivered**. Clair Health failed on the KNOWN ~one-per-run fit-brief JSON-truncation
bug (`fit-brief-json-truncation-known-bug`) — the runner **isolated it** (per-company recovery, not checkpointed →
auto-retries next run) and now **surfaces the reason** on the `/research` page + email (a gap the live test exposed,
fixed same session). Out-of-taxonomy Sandbar was NOT force-fit (segment/business_model/bg None) → landed P3 / final 8.0
/ `low_score_floor` (correct bottom-of-roster). Email path also needed a **User-Agent header** (Cloudflare 403s the
default python-urllib agent — fixed). Resend live-verified (test + run emails delivered to lavallee.kj@gmail.com).
Suite **731**. **Remaining (slice 5 ops, to deploy):** upgrade Render to **Starter** + attach the 1 GB disk at
`/var/htra`; add `RESEND_API_KEY` in Render (render.yaml declares all three). Then merge → deploy (also brings the
new tabbed header UI live).

**UI cleanup pass (2026-07-05, on the same branch):** unified light-header **tabs** (Career Dashboard / Company
Discovery / Review Pipeline) across all pages via `webapp/chrome.py`; navy title banner removed; Refresh folded into
the dashboard; a "Research running…" status strip links to `/research` (which is reached by auto-redirect on approve,
not a tab). Deploys with the phase.

**✅ RESOLVED 2026-07-05 — the two "must-fix" items + a real dashboard bug the batch exposed:**
1. **NON-ISSUE (a mis-read, not a bug).** The original "non-health → all-None" diagnosis was a FALSE ALARM — I read
   the WRONG JSON keys (`sb.get("segment")` instead of nested `taxonomy.segment`; a nonexistent `background_fit` key).
   Sandbar actually classified **correctly**: `taxonomy.segment=OTHER_REVIEW` ("Other"), `business_model=B2C`, PATH gate
   PASSED on B2C direct revenue (health-agnostic), AGENCY PASSED, `model_priority=P3` (floored). The one real value,
   `bg_fit=4`, **STANDS** — the read correctly judged Sandbar's engagement as episodic (a conversational voice ring, no
   daily loop); Katelynd overrides manually if her deep-dive warrants. No code change. *Reference — the engagement-fit
   rubric (Katelynd 2026-07-05): `background_fit` scores the user ENGAGEMENT PATTERN + how tied it is to the REVENUE
   engine, health-agnostic — biometric feedback loop = top; daily habitual engagement tied to revenue = medium–strong;
   infrequent = weak.*
2. **FIXED — fit-brief JSON truncation (~one/run).** On a parse failure the batch now retries the fit brief ONCE at
   `FIT_BRIEF_RETRY_TOKENS=12000` (was a fixed 6500); same prompt, never worse. Live-proof on the next run (recurs
   every run, so we'll know immediately). See `fit-brief-json-truncation-known-bug`.
3. **FIXED — dashboard 500 on un-reviewed entries.** The runner merges new companies UN-reviewed (pending GATE-2), but
   `build_dashboard` raised on any un-reviewed entry (§1a) → the live dashboard 500'd right after the batch merged
   Sandbar. Now `build_dashboard(skip_unreviewed=True)` (webapp) shows REVIEWED companies + excludes pending ones (they
   appear once finalized at GATE-2); the Colab-regen flow keeps the raise-guard by default. The dashboard now survives
   every research batch.

**NEXT (front end is done — these are the remaining, non-blocking follow-ups; doc-first):**
- **Batch-storage upgrade** — `research.csv` is a single append-only file (the SA can't create per-batch files —
  `sa-cannot-create-drive-files`). Current writes are guarded + write-once. To properly support **re-research as a new
  dated entry** (not just new companies), add a `batch_id`/`date` column, append-only, read = latest-per-company. Do
  this BEFORE ever re-researching an existing company. Optional extra safety: a pre-created `research_backup.csv`.
- **Paste-one-corrected-fact re-score path** (Carry-forward notes).
- **Non-health segment routing (minor calibration, 2026-07-06):** in the live test, **Suno** landed in the generic
  **`OTHER_REVIEW` ("Other")** catch-all instead of **`ENTERTAINMENT_TECH`** — even though Suno is the taxonomy's own
  example for Entertainment tech. The non-health classifier reaches the generic catch-all but not the specific
  non-health categories (Entertainment / Fintech). Low priority (non-health companies floor to P3 regardless, and the
  segment is human-overridable); revisit if the specific non-health category matters. NOT the earlier false-alarm Bug 1.

Local run/preview quirks (Python 3.9 box): see the `local-dev-env-python39` memory.

> **The human GATE-2 review runs NOW** against the live CSV packet: set priority overrides in `cards.csv`,
> merged back into the ledger via `ledger.apply_gate2_decisions` (priority-only; scores never hand-edited).
> The regen-2 batch was reviewed 2026-07-03 (5 overrides applied). This is a USE of the built packet, not a
> build milestone.

*This section is the single status record (replaces the standalone PROJECT_TRACKER.md). Update it as
milestones move; keep done/next honest.*

## Carry-forward engineering notes (open, not yet built)
- **Batch research storage — new CSV per batch (DECIDED 2026-07-04).** Ongoing research runs in batches of 5–10
  companies; each batch writes its OWN immutable research CSV — never append to / mutate a prior file (Rule 8 /
  append-only; strongest "never touch existing data" guarantee). The ledger already accumulates (score-once-on-entry,
  append per batch) and GATE-2 finalize stamps only the NEW entries, so a batch's GATE 2 = only its new companies.
  **Near-term front-end change (not yet built):** the dashboard Google source must read + COMBINE all research CSVs in
  the Drive folder (today it reads a single `research.csv`) so a new batch appears with zero risk to old data.
- **Research update / re-score flow — OPEN design item (2026-07-04; touches the LOCKED write-once-scores rule → spec
  DOC-FIRST before building).** Two human-initiated ways to update an already-scored company, BOTH creating a NEW
  DATED ledger entry (old kept as history, nothing edited in place — write-once preserved; latest wins): (1) full
  re-research; (2) a FAST "human-augmented re-score" — copy the existing research forward, add ONE human-provided fact
  (e.g. "Series B $35M"), re-score WITHOUT the ~20-min full research (Katelynd's rationale: re-research is slow, and a
  fact the thorough research layer missed once it will likely miss again). Rule-consistent: the human supplies
  EVIDENCE, the deterministic scorer still DECIDES (Rule 7). **Crux to design (the plausible-but-wrong trap):** the
  scorer reads STRUCTURED fit-brief fields, NOT raw pasted text — so a pasted fact must be turned into the structured
  field(s) the scorer consumes (a tiny LLM re-extraction pass over findings+fact, OR direct structured-field entry) or
  the re-score SILENTLY no-ops. Also: tag the human-provided fact's provenance (human vs research-gathered) and
  reconcile with any existing human priority override (Rule 6). Does NOT block the front-end Phase 1.
- **GATE-2 review data findings (regen-2 batch, 2026-07-03)** — surfaced during the live GATE-2 review; each
  is an UPSTREAM/research fix (Rule 8 — do NOT hand-edit the ledger): (1) **`cylinder health` = `vivante health`**
  are the SAME company (Cylinder is the rebrand of Vivante) — de-dup the candidate/research set (drop `vivante`).
  (2) **`rula health` Series C date** reads `2026-02` but the real Series C closed **July 2024** — check the
  round's designation/date in the research (a later same-series round may be mislabeled series-c). (3) **`pomelo
  care` growth** came back UNKNOWN (fenced on covered-lives) — verify a real revenue-growth data point wasn't
  missed in research. Katelynd's 5 priority overrides (function→P1, grow→P3, rula→P1, bicycle→P1, summer→P2)
  live in the ledger's decision block with history (Rule 6), NOT here.
- **Fit-brief JSON-retry hardening** — the research fit-brief occasionally fails with a `JSONDecodeError`
  (the `videahealth`-class failure; happens ~once per run and can drop a company). Retry/repair the fit
  brief on decode failure. Real, recurring; not yet built.
- **Ledger-review watch-item (data credibility)** — several HIGH growth bands rest on GetLatka `$0→$N`
  single-source series where "$0 in year one" may reflect missing early data rather than a true zero
  (`fay` / `foodsmart` / `nourish` / `berry street` / `summer` / `visana`). Surface in the ledger review
  — NOT a scoring fix. Detail: `archive/specs/PHASE3_PROCESS_HISTORY.md` "Known watch-items."
- **Classifier wobble on borderline B2B/B2B2C** — a FRESH classifier read can flip a non-locked borderline
  company between B2B and B2B2C run-to-run (e.g. `angle health` read B2B on the 2026-07-03 run → wrongly
  floored with `n/a` scores; it's a consumer health plan → should be B2B2C). The 6 human-locked B2B-floor
  companies are stable; only NON-locked borderline ones wobble. The ledger's `n/a` display makes such a
  misclassification VISIBLE at review. Calibration item — consider extending the locked list / hardening the
  §B2 classifier; do NOT hand-edit the ledger (Rule 8).
- **`run_r1` cache not auto-persisted (Rule 4 gap)** — the R1 read-cache lives only in memory, so a Colab
  disconnect loses it and forces re-taking the LLM reads (cost + re-roll). Hardening: auto-save the cache to
  Drive as reads are taken + reload on resume. A manual `json.dump(rep["cache"], …)` currently covers it.
- **Parked side-task — Claude Code approval-prompt hook** — a PreToolUse auto-approve hook to cut constant
  approval prompts; full spec archived at `archive/specs/spec_pretooluse_autoapprove_hook.md`. Not started.

> Scoring-model open items (e.g. the PATH Test B employer-direct institutional-channel scope fix, and the
> ^c3 B2C viable-engine LINE) live in `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` §B3 — that's their home, not here.

## Verification anchors
- **ZOE** = canonical reset test case; **Function Health** = canonical maturity/commercial test case.
- Code logic is proven offline (red→green unit tests); notebook wiring + real-LLM-output behavior are
  proven only by a live Colab run. Package-green is necessary, not sufficient.
