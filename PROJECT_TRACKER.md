# Health Tech Research Agent — Build Tracker

A working checklist for completing the agent, from the current dashboard milestone through full orchestration. Update the status marks as you go.

Status key: `[x]` done · `[~]` in progress · `[ ]` not started

Two environments matter throughout:
- **Local / Claude Code** — writing and unit-testing package functions. No access to your live batch state, Google Sheets, or research APIs.
- **Live / Colab** — running real batches against the actual master and Google Sheets, where runtime state (e.g. `boston_blind_spot_batch_1`) lives. Some steps can only be verified here.

---

## Phase 0 — Already complete (foundation)

- [x] Persistent workflow foundation — BatchManifest, batch states, durable resume points, atomic CSV/JSON writes, resume without re-research, regression coverage
- [x] Review packet publication & reconciliation — guarded Sheets publication, exact batch-ID/company-set validation, read-back verification, idempotent adoption, human decisions preserved
- [x] Human review-decision validation — APPROVE / HOLD / REJECT handling, required-field & consistency checks, validated decision audit, approved-only master-update artifact
- [x] Transactional master update — in-memory build, override protection, model-vs-reviewed priority kept separate, backup + atomic write, read-back, rollback, field-level change log (verified live: 8 updates, 127 field changes, 0 duplicates)

---

## Phase 1 — Current milestone: dashboard rebuild & completion validation

Goal: get `boston_blind_spot_batch_1` from `ERROR_REQUIRES_REVIEW` / `REFRESH_DASHBOARD` to a validated `COMPLETE`.

### Code (Claude Code, branch `taxonomy-precedence-merge`)
- [x] Taxonomy precedence merge — collapse duplicate `classify_dataframe`, restore override-first order (commit `11b129b`)
- [x] Calibration-flag recompute — migrate `build_calibration_flag` to `priority.py`, recompute from final priority on rebuild (commit `e3e57a1`)
- [~] Package-level dashboard rebuild in `workflow.py` — load verified master → reclassify → recompute flags → build tabs → atomic write → read-back + structural/field validation → completion report → advance to COMPLETE only on success
- [ ] Review all three commits together; confirm failure-injection tests prove the gate still refuses to advance on a bad workbook
- [ ] Open PR for the dashboard milestone (all three commits as one reviewed unit)
- [ ] Merge to `main`

### Live verification (Colab — neither chat nor local Claude Code can do this)
- [ ] Run the repaired rebuild against the live batch from `ERROR_REQUIRES_REVIEW` / `REFRESH_DASHBOARD`
- [ ] Confirm the completion report shows the expected figures (stale flags cleared, override segments reconciled) matching the original failure
- [ ] Confirm the batch transitions to `COMPLETE` and the rebuilt workbook passes full validation
- [ ] Confirm master and prior dashboard remained untouched throughout

### Housekeeping (low priority, do when convenient)
- [ ] Fill in the real `Commands` section of `CLAUDE.md` from `pyproject.toml`
- [ ] Add `.DS_Store` to `.gitignore`

---

## Phase 2 — Harden the research front half

The biggest gap between "polished back half" and "agent a user can actually ask to find companies." Order matters: extract the research runner first, since everything else here depends on it.

- [ ] **Extract the research runner into the package** — package-level function with retries and per-company recovery, out of notebook logic (Step 4 / Step 7). *Highest leverage; do first.*
- [ ] Raw archive & data-depth remediation rules — move into package functions
- [ ] Candidate discovery function — source-backed rationale, out of manual/notebook research
- [ ] Deduplication against master and current batches
- [ ] Initial triage — research now / watch / reject
- [ ] Persistent candidate proposal artifact — durable, source-backed shortlist
- [ ] First human approval gate — durable candidate review surface + explicit approval state (the front-half equivalent of your working Step 6 review gate)

Each piece: same discipline as Phase 1 — implement, red→green tests, stop for review, separate commit.

---

## Phase 3 — Critical recommendation layer

- [ ] Dedicated critical-review function after research (currently no agent-level step orchestrated end to end)
- [ ] Recommendation rationale tied to evidence quality and role/operator timing
- [ ] Explicit uncertainty & missing-evidence requirements
- [ ] Structured recommendation artifact produced before the second human review

---

## Phase 4 — Orchestrator & interface (build last)

Wire together functions that already work; do not start until the underlying steps are real package functions.

- [ ] State-machine orchestration across all user-facing stages
- [ ] Agent tool calls into the deterministic package functions (the agent orchestrates tools; it does not replace them with free-form reasoning)
- [ ] User-facing interface for approvals, errors, and completion
- [ ] Run observability — API usage, cost, runtime tracking
- [ ] Prompt / version registry + benchmark regression suite

---

## Definition of done (from your status doc — the finish line)

- [ ] A user can request market discovery without editing code
- [ ] The agent proposes a source-backed candidate list and waits for approval
- [ ] Approved candidates are researched with per-company checkpointing and recovery
- [ ] The agent produces a critical recommendation packet and waits for a second human decision
- [ ] Approved decisions update the master transactionally and refresh the dashboard
- [ ] The system validates the final master and workbook, writes completion artifacts, reports success or a recoverable error
- [ ] A runtime disconnect at any point resumes from the last durable state without repeating completed work
- [ ] All major logic has regression tests; no production behavior depends on notebook cell order

---

## Working habits that have served this project well

- Three separate, approved steps per change: **investigate cause → plan (no code) → implement (one commit)**.
- For every fix, demand the **red→green proof**: the test must fail on the pre-fix behavior and pass after. A test that passes on both broken and fixed code guards nothing.
- **Plan mode on**; review the diff before approving.
- Land logically-coupled changes as **one reviewed milestone**, not partial PRs onto `main`.
- Never weaken a validation gate to make a batch pass — **fix the inputs, not the checks**.
- Model setting: **Opus 4.8 + "smarter"** for diagnosis/planning; **Sonnet 4.6 + balanced** for routine execution.
