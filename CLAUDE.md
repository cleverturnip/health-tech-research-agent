# CLAUDE.md

Standing instructions for working in this repository. Read this fully at the start of every session before proposing or making changes.

## What this project is

A health tech company research agent. The end goal is an agent a user can ask to discover companies, that proposes a source-backed candidate list, researches approved companies, produces a critical recommendation packet, applies approved decisions to a master record transactionally, and refreshes a dashboard — with human approval gates and full resumability throughout.

The codebase is being migrated out of Google Colab notebook cells into version-controlled, importable package functions. That migration is the central engineering effort. Treat any notebook-style pattern as something to replace, not extend.

## Architecture rules (locked — do not violate)

These are non-negotiable. If a requested change would break one of these, stop and say so rather than proceeding.

1. New production behavior must be implemented as importable package functions, NOT new notebook cells, dynamic globals patches, or code that depends on cell execution order.
2. Google Colab is the development and testing shell, not the production architecture. Do not add logic that only works inside Colab.
3. Google Sheets remains the human review surface. Do not replace it or route human decisions elsewhere.
4. Every state transition must be persistent, validated, and resumable after a runtime loss. A disconnect at any point must resume from the last durable state without repeating completed work.
5. No step may mark success before its durable artifacts are reopened and verified (read-back validation). "Wrote the file" is not "done"; "reopened the file and confirmed its contents" is "done."
6. Human-reviewed priority and taxonomy overrides ALWAYS take precedence over model-generated values. Never overwrite a human override with an automated value.
7. The agent orchestrates deterministic tools; it does not replace them with free-form reasoning. The LLM gathers and interprets evidence. Deterministic rules decide priority. Human review handles only true edge cases.
8. Incorrect outputs are calibration data that should improve the decision logic — not something to fix by manual spreadsheet editing.

## How I want you to work

- **Plan before acting.** For anything beyond a trivial edit, show me the plan and wait for approval before changing files. I am not a coder; explain what you're about to do in plain language first.
- **Small, reviewable changes.** Prefer focused commits I can understand and roll back. Confirm the working tree is committed before large edits.
- **Run the tests.** After changes, run the test suite and report what passed and failed. Do not tell me something works until the tests and read-back checks confirm it.
- **Don't mark anything complete prematurely.** Follow rule 5 above. Reopen and verify artifacts.
- **Ask when unsure.** If a request is ambiguous or seems to conflict with the locked rules, ask rather than guessing.
- **Respect the existing safety model.** This project deliberately refuses to advance state against stale or unvalidated artifacts. Preserve that behavior; never weaken a validation gate to make a batch pass.
- **Keep the runbook in sync — and put fixes in it.** The run-once regeneration runs step-by-step from the written runbook: `specs/regen_execution_runsheet.md` (cell-by-cell Colab steps + recovery/troubleshooting) and `specs/phase2_refresh_runbook.md` (the pre-regen gate). Whenever we change a cell, fix a bug, or learn an operational lesson mid-run, write it into the runbook the *same turn* — never leave a fix living only in chat. A stale runbook is a real hazard on an unforgiving run-once.
- **OpenAI "rate limit" errors during research usually mean OUT OF CREDITS, not throttling.** A sustained `Rate limit hit … Max retries reached` (429s on the first request, never eases) is almost always `insufficient_quota` — check platform.openai.com billing/credits + the monthly auto-recharge cap before assuming rate limits. See the runbook's "CHECK BILLING FIRST" section.

## Priority model

> ⚠️ **REDESIGNED — see `specs/MASTER_REDESIGN_SPEC.md` (RECONCILED v1, 2026-06-30).** The master is now the
> **GATE-2 scoring-review ledger** (the ONE master; supersedes the V4.2/V1 data master — raw research data
> lives in the research output). Priority comes from the **§B scoring system**
> (`specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`), not `candidate_priority`. The **six columns below RETIRE**;
> the ledger uses a clean from-scratch model: `model_priority` (§B tier) · `human_override` (+`reason`) ·
> `final_priority` (override else model; DERIVED) · `provenance` (override-only; DERIVED) · `history`
> (append-only) · `framework_version` (per-entry staleness) · `taxonomy_override` (+`reason`). `code`/`rank`
> derive on read; domain is now **P0–P3** (no P4). The **decision block edits PRIORITY + TAXONOMY only (Rule
> 6); scores + research data are write-once, never hand-edited (Rule 8)**. The descriptions below are
> HISTORICAL (the old data-master model).

| Priority | Meaning |
|----------|---------|
| P0 | Highest-priority target / active pursuit |
| P1 | Near-priority target / former P1-border |
| P2 | Worth deeper diligence |
| P3 | Watch list |
| P4 | Low priority / likely reject |

Priority source fields, kept separate for traceability:

- `priority_level` — automated/adjudicated system priority
- `reviewed_priority_level` — optional human override
- `final_priority_level` — dashboard priority after normalization
- `priority_source` — `Auto Adjudicated` or `Human Reviewed`
- `final_priority_code` — P0/P1/P2/P3/P4
- `final_priority_rank` — numeric sort helper

Model priority and reviewed priority must be preserved separately; do not collapse them.

## End-to-end user flow and current status

1. User asks the agent to discover companies — **NOT STARTED**
2. Agent proposes candidate companies — **NOT STARTED**
3. User approves / removes / adds candidates (first human gate) — **NOT STARTED**
4. Agent researches approved companies and produces a review packet — **PARTIAL** (research runner still lives mainly in notebook logic; persistent resume and review-packet publication are hardened)
5. Agent critically reviews findings and recommends priorities — **PARTIAL** (scoring, scale engine, calibration flags, deterministic adjudication, taxonomy exist; dedicated agent-level critical-review step not yet orchestrated)
6. User approves / holds / rejects recommendations — **COMPLETE**
7. Agent commits approved decisions to the master and refreshes the dashboard — **IN PROGRESS** (transactional master update complete; dashboard rebuild + read-back + completion transition is the active milestone)
8. Agent audits final outputs and reports completion — **IN PROGRESS**

## Current milestone (work here first)

Dashboard rebuild and completion validation.

- Live batch: `boston_blind_spot_batch_1`
- Persistent state: `ERROR_REQUIRES_REVIEW`
- Resume point: `REFRESH_DASHBOARD`
- Why it stopped: the existing dashboard workbook was correctly rejected as stale — it still contained stale calibration flags, and the validator surfaced market-segment comparison issues requiring corrected precedence logic.
- Safety result so far: master unchanged, prior dashboard unchanged, batch correctly NOT marked complete.

Patch in progress: package-level dashboard rebuild, corrected taxonomy-label precedence, workbook read-back validation, completion report, and a transition to COMPLETE only after success.

Do not mark this batch complete until the rebuilt workbook passes full validation.

## What's already done (don't rebuild without reason)

- Persistent workflow foundation: BatchManifest, explicit batch states, durable resume points, atomic CSV/JSON writes, resume without rerunning completed research, regression coverage for state transitions.
- Review packet publication and reconciliation: guarded Google Sheets publication, exact batch-ID and company-set validation, read-back verification, idempotent adoption of an already-correct sheet, human decisions preserved.
- Human review-decision validation: APPROVE / HOLD-NEEDS_MORE_RESEARCH / REJECT handling, required-field and consistency checks, validated decision audit artifact, approved-only master-update artifact.
- Transactional master update: build proposed master in memory, protect human taxonomy overrides, preserve model priority separately from reviewed priority, backup before mutation, atomic write, read-back verification, automatic rollback on failure, field-level change log. (Verified live: 8 updates, 0 inserts, 127 field changes, 0 duplicates.)

## Remaining work, in the order I want to tackle it

1. **Finish the post-research pipeline** (current milestone): dashboard rebuild from verified master, structural + field-level workbook validation, persist validation/completion reports, advance to COMPLETE only after read-back, then commit/push/PR/merge.
2. **Harden the research front half**: extract the package-level research runner (with retries and per-company recovery) out of notebook logic first — most other front-half work depends on it. Then candidate discovery with source-backed rationale, dedup against master and current batches, initial triage (research now / watch / reject), persistent candidate proposal artifact, and the first human approval gate.
3. **Add the critical recommendation layer**: dedicated critical-review function after research, recommendation rationale tied to evidence quality and role timing, explicit uncertainty / missing-evidence requirements, structured recommendation artifact before human review.
4. **Build the orchestrator and interface last**: state-machine orchestration across all stages, agent tool calls into the deterministic package functions, a user-facing surface for approvals/errors/completion, run observability (API usage, cost, runtime), and a prompt/version registry with a benchmark regression suite. Build this only once the underlying steps are working functions.

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
- `taxonomy/` — taxonomy definitions
- `tests/` — regression and failure-check tests
- `maintenance/` — maintenance / rescore / repair flows only (not part of the normal batch run)
- `colab_workflow.py` — working Colab code, organized by numbered steps; the migration source
- `workflow_tracker.md` — step-by-step run order and step definitions
- `workflow_runbook.md` — operational runbook
- `README.md` — project overview

Note: the numbered run order in `workflow_tracker.md` (1 → 2 → ... → 19A) reflects notebook cell sequencing. The migration goal is to turn those steps into functions with explicit arguments and return values so the orchestrator can call them — not to preserve the linear cell order.

## Commands

<!-- Fill these in from pyproject.toml / your actual setup, then commit. Examples below — replace with the real ones. -->

- Install (editable): `pip install -e .`
- Run tests: `pytest`
- (add lint / type-check / batch-runner commands here as they exist)
