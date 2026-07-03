# CLAUDE.md

Standing instructions for working in this repository. Read this fully at the start of every session before proposing or making changes.

## What this project is

A health tech company research agent. The end goal is a mostly-autonomous flow bounded by two human approval gates: the user defines a target market and approves a proposed candidate list (GATE 1); an autonomous segment researches the approved companies, scores them into a scoring ledger, and produces review cards + a summary table with recommendations (GATE 2); a second autonomous segment builds the dashboard — with full resumability throughout. Between gates there is zero user input; a problem inside a segment is handled autonomously or surfaced for review at the next gate.

The codebase is being migrated out of Google Colab notebook cells into version-controlled, importable package functions. That migration is the central engineering effort. Treat any notebook-style pattern as something to replace, not extend.

## Architecture rules (locked — do not violate)

These are non-negotiable. If a requested change would break one of these, stop and say so rather than proceeding.

1. New production behavior must be implemented as importable package functions, NOT new notebook cells, dynamic globals patches, or code that depends on cell execution order.
2. Google Colab is the development and testing shell, not the production architecture. Do not add logic that only works inside Colab.
3. CSV outputs are the current human-review surface — human decisions (approvals / edits / overrides at the gates) are made against those artifacts and read back from them. (Google Sheets was the prior surface and is superseded; a purpose-built front end is the eventual surface.) Do not route human decisions through a non-durable or unreviewed channel. **Scope:** this rule governs GATE decisions. The post-GATE **dashboard** is a separate, format-fluid working tracker (not a gate-decision channel); its editable store is a native Google Sheet, read INPUT-ONLY so the build never overwrites your edits (see `specs/DASHBOARD_DESIGN.md`).
4. Every state transition must be persistent, validated, and resumable after a runtime loss. A disconnect at any point must resume from the last durable state without repeating completed work.
5. No step may mark success before its durable artifacts are reopened and verified (read-back validation). "Wrote the file" is not "done"; "reopened the file and confirmed its contents" is "done."
6. Human-reviewed priority and taxonomy overrides ALWAYS take precedence over model-generated values. Never overwrite a human override with an automated value.
7. The agent orchestrates deterministic tools; it does not replace them with free-form reasoning. The LLM gathers and interprets evidence. Deterministic rules decide priority. Human review handles only true edge cases.
8. Incorrect outputs are calibration data that should improve the decision logic — not something to fix by manual spreadsheet editing.
9. Absence is an upper bound, not a measurement. A blank or "not found" in our OWN output means the data isn't in our output — it does NOT establish the data doesn't exist ("truly absent" and "present but our pass missed it" produce an identical blank). Never attribute a cause to an empty field from the output alone; convert the bound to a measurement with a live test that actually goes looking (e.g. a repeat-N variance probe) before building on the attribution.

## How I want you to work

- **Plan before acting.** For anything beyond a trivial edit, show me the plan and wait for approval before changing files. I am not a coder; explain what you're about to do in plain language first.
- **Small, reviewable changes.** Prefer focused commits I can understand and roll back. Confirm the working tree is committed before large edits.
- **Run the tests.** After changes, run the test suite and report what passed and failed. Do not tell me something works until the tests and read-back checks confirm it.
- **Don't mark anything complete prematurely.** Follow rule 5 above. Reopen and verify artifacts.
- **Package-green is necessary, not sufficient.** For anything wired into the notebook, "done" also requires mirroring the change into the live-region notebook cells and a live Colab run — offline unit tests can't prove notebook wiring or real-LLM-output behavior. (Extends rule 5's read-back discipline to the notebook boundary.)
- **Intent-to-action confirmation.** When a recorded intent isn't directly, unambiguously actionable — turning it into a concrete rule/threshold/mechanism requires choosing among interpretations — STOP and confirm the exact translation before building or documenting it. Don't fill the gap with the most plausible reading; the plausible-but-wrong interpretation is the recurring failure mode (it passes review because it reads reasonably, and only a live run exposes it). If you can't state the rule the way I'd recognize as exactly what I meant, you're interpreting, not implementing — surface it.
- **Doc-first for scoring/framework changes.** The scoring + priority framework has ONE source of truth (`specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`). Any scoring-logic change edits that doc FIRST (version bump) and is committed as its own commit BEFORE building anything that depends on it. If a locked decision isn't in the doc, it isn't locked.
- **LLM-facing prompt wording is the highest-stakes change.** Design prompt wording with me explicitly and get sign-off before building — a wording change can silently shift every downstream result.
- **Capture decisions durably.** Nothing important lives only in chat — put decisions and fixes into the repo (specs / runbook / status) the same turn.
- **Ask when unsure.** If a request is ambiguous or seems to conflict with the locked rules, ask rather than guessing.
- **Respect the existing safety model.** This project deliberately refuses to advance state against stale or unvalidated artifacts. Preserve that behavior; never weaken a validation gate to make a batch pass.
- **Keep the runbook in sync — and put fixes in it.** The run-once regeneration runs step-by-step from the written runbook: `specs/regen_execution_runsheet.md` (cell-by-cell Colab steps + recovery/troubleshooting) and `specs/phase2_refresh_runbook.md` (the pre-regen gate). Whenever we change a cell, fix a bug, or learn an operational lesson mid-run, write it into the runbook the *same turn* — never leave a fix living only in chat. A stale runbook is a real hazard on an unforgiving run-once.
- **OpenAI "rate limit" errors during research usually mean OUT OF CREDITS, not throttling.** A sustained `Rate limit hit … Max retries reached` (429s on the first request, never eases) is almost always `insufficient_quota` — check platform.openai.com billing/credits + the monthly auto-recharge cap before assuming rate limits. See the runbook's "CHECK BILLING FIRST" section.

## Priority model

The scoring + priority framework has ONE source of truth: `specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` (the §B scoring system, FRAMEWORK_VERSION-stamped). Priority is produced by that model and written write-once into the GATE-2 scoring-review ledger; the ledger's structure (`model_priority` · `human_override` · `final_priority` · `provenance` · `history` · `framework_version` · `taxonomy_override`; domain P0–P3) is specified in `specs/MASTER_REDESIGN_SPEC.md`. Human priority/taxonomy overrides always win (Rule 6); scores are never hand-edited (Rule 8). Don't restate scoring or priority-field definitions here — change them in the SOT, which version-bumps.

## Current status, milestone, and roadmap

Status lives in ONE place — `specs/COLLABORATION_CONTEXT.md`, the "Status & roadmap" section. Read that section at the start of every session; it is the single source for where we are, what's done, and what's next (this replaces the old status list here and the standalone `PROJECT_TRACKER.md`). Do not track status in this file — keeping a second copy here is what caused the drift this points away from.

## Definition of done for the full agent

- A user can request market discovery without editing code.
- The agent proposes a source-backed candidate list and waits for approval.
- Approved candidates are researched with per-company checkpointing and recovery.
- The agent produces a critical recommendation packet and waits for a second human decision.
- Approved decisions update the master transactionally and refresh the dashboard.
- The system validates the final master and workbook, writes completion artifacts, and reports success or a recoverable error.
- A runtime disconnect at any point resumes from the last durable state without repeating completed work.
- All major logic has regression tests, and no production behavior depends on notebook cell order.

## Repo layout (verify against the working tree)

- `src/health_tech_research_agent/` — the package; new functions belong here
- `specs/` — current specs and context. Key docs: `COLLABORATION_CONTEXT.md` (flow + status/roadmap), `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` (scoring), `MASTER_REDESIGN_SPEC.md` (ledger + cards design), `DASHBOARD_DESIGN.md` (the built dashboard segment: design + Colab run steps; `dashboard_wireframe.html` is the visual reference); also the active regen runbooks (`regen_execution_runsheet.md`, `phase2_refresh_runbook.md`)
- `taxonomy/` — taxonomy definitions
- `tests/` — regression and failure-check tests
- `maintenance/` — maintenance / rescore / repair flows only (not part of the normal batch run)
- `colab_workflow.py` — working Colab code, organized by numbered steps; the migration source
- `archive/` — superseded/historical docs kept for reference (process history, finished slice specs, audits, one-off probe scripts, the old notebook workflow docs); not current guidance
- `README.md` — project overview

## Commands

- Install (editable): `pip install -e .`
- Run tests: `pytest`
- (add lint / type-check / batch-runner commands here as they exist)
