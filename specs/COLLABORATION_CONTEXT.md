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
6. `specs/FRONT_END_PHASE1_HOSTED_DASHBOARD.md` — the Phase-1 (hosted dashboard) BUILD SPEC: contract for the
   first front-end phase (FastAPI + Render, password login, least-privilege Google read, on-the-spot Refresh).
7. `specs/SCORING_WALKTHROUGH.md` — plain end-to-end walkthrough of how a company gets scored.
8. `specs/regen_execution_runsheet.md` + `specs/phase2_refresh_runbook.md` — regeneration runbooks (active).
9. `CLAUDE.md` — Claude Code's working rules and repo map.

Superseded/historical material (finished slices, the old `candidate_priority` engine, Phase-3 process
history, audits, one-off probes) lives in `archive/` — reference only.

## Status & roadmap (single source of truth for where we are)

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

**Phase 1 — hosted dashboard: BUILT + LOCALLY LIVE-VERIFIED (2026-07-04), merged to `main`.** The FastAPI web
shell (`src/health_tech_research_agent/webapp/`) over the existing dashboard engine (Rule 1): simple-password
login + session gate; on-the-spot Refresh (rebuilds from Google, visible overlay, keeps your tab); a Google-backed
source that reads `ledger.jsonl` + the research CSV from a shared Drive folder + the dashboard Sheet via a
least-privilege service account; **in-app `pursue` editing** writes one cell back to the Sheet (read-back verified;
narrowly widened the Sheet scope to write — spec §8a). Polished analytics UI (navy/blue-ramp/cyan/gold reference
palette, KPI tiles, dark table headers + zebra, segment-radar chart, colored company-detail view). Verified end-to-end
against Katelynd's real Google data (54 companies); 667 tests. Also fixed a dup-column bug (reference columns leaking
into the user layer). **NEXT: Step 3 — deploy to Render** (Katelynd's Render account + moving the local settings into
Render secrets) then **Step 4 — live-verify on the hosted URL** (`FRONT_END_PHASE1…md` §6–8). Then Phase 2 (in-app
GATE-2 review). Local run/preview quirks (Python 3.9 box): see the `local-dev-env-python39` memory.

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
