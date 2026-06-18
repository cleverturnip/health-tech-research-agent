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

## Phase 1 — Dashboard rebuild & completion validation (done; live verification pending in Colab)

Goal: get `boston_blind_spot_batch_1` from `ERROR_REQUIRES_REVIEW` / `REFRESH_DASHBOARD` to a validated `COMPLETE`.

### Code (Claude Code, branch `taxonomy-precedence-merge`)
- [x] Taxonomy precedence merge — collapse duplicate `classify_dataframe`, restore override-first order (commit `11b129b`)
- [x] Calibration-flag recompute — migrate `build_calibration_flag` to `priority.py`, recompute from final priority on rebuild (commit `e3e57a1`)
- [x] Package-level dashboard rebuild in `workflow.py` — load verified master → reclassify → recompute flags → build tabs → atomic write → read-back + structural/field validation → completion report → advance to COMPLETE only on success (commit `cb65d94`)
- [ ] (deferred) Port remaining notebook dashboard tabs into `build_workbook_sheets` — Priority Focus, Candidate P0/P1, Companies by Segment, Segment Coverage Audit, Data Depth Audit, Priority Comparison, Commercial Scale Review, Priority Logic Audit, Read Me. Core 4-sheet workbook ships now; these are additive and can be added later if needed.
- [x] Review all three commits together; confirm failure-injection tests prove the gate still refuses to advance on a bad workbook
- [x] Open PR for the dashboard milestone (all three commits as one reviewed unit) — [#22](https://github.com/cleverturnip/health-tech-research-agent/pull/22)
- [x] Merge to `main` (PR #22, merge commit `d35c421`)
- [x] Make manifest loading tolerant of unknown/legacy artifact keys (found in live verification: the live manifest carried `dashboard_validation_path`) — keeps batches resumable across schema drift (PR #23, merged + live-verified)

### Live verification (Colab — neither chat nor local Claude Code can do this)
- [ ] Run the repaired rebuild against the live batch from `ERROR_REQUIRES_REVIEW` / `REFRESH_DASHBOARD`
- [ ] Confirm the completion report shows the expected figures (stale flags cleared, override segments reconciled) matching the original failure
- [ ] Confirm the batch transitions to `COMPLETE` and the rebuilt workbook passes full validation
- [ ] Confirm master and prior dashboard remained untouched throughout

### Housekeeping (low priority, do when convenient)
- [ ] Fill in the real `Commands` section of `CLAUDE.md` from `pyproject.toml`
- [ ] Add `.DS_Store` to `.gitignore`

---

## Phase 2 — Current milestone: harden the research front half

The biggest gap between "polished back half" and "agent a user can actually ask to find companies." Order matters: extract the research runner first, since everything else here depends on it.

> **Why this is the current milestone.** Extracting the research runner into the package is the unblocking task. Real capability-fit (Phase 3) needs the fit-brief prompt to gain the capability-fit field *in the package* (not the notebook), which requires the research runner to live in the package first. The dependency cascades: research runner → real capability-fit → Commit 5 (candidate → `final_priority_level` authority) → Commit 6 (master remediation).

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

> **Relationship to the engine below.** The *deterministic priority core* of this layer is now built — see "Candidate Priority Engine" below. What remains of the original recommendation-layer vision (the four bullets above) is the **LLM-assessment / recommendation-summary layer that sits on top of the engine**: the step where the LLM reviews the engine's deterministic output and brings recommended priority changes (and additional-research flags) to the human review gate. The engine is the deterministic foundation; these bullets are the LLM layer on top of it. (Per Rule 7: the engine decides priority deterministically; the LLM only gathers evidence beforehand and recommends afterward.)

### Candidate Priority Engine (deterministic; shipped — framework "V4.2-interim")
- [x] Commit 1 — signal conversion + reconciled scale-path; single source-of-truth vocabulary + closure test (commit `2023dca`)
- [x] Commit 2 — agency-entry + archetype producers (verbatim cell159) + shared `reset_signal` text-scan, no hardcoded company names (commit `f06ccca`; §5a fixup `514aac8`)
- [x] Commit 4 — V4.1 gate + V4.2 public/near-IPO cap + `compute_candidate_priority` orchestrator; emits P0–P3 only (commit `760e958`)
- [x] Merge to `main` (PR #24)
- [x] Commit A — reset reads the researched `reset_or_restructure_signal` field; text-scan retired (fixes the audit's 6 false-positive / 1 false-negative finding: videahealth-type incidental "integration", ZOE-type manual override) (PR #27)
- [x] Commit B — P0 scale-path accepts strong commercial OR institutional OR dual; standalone `institutional ≥ 3` dropped so strong-D2C (e.g. Oura) can reach P0. Strict `commercial == 3` definition and all other P0 conditions unchanged (PR #27)
- [ ] (deferred) Real LLM-scored capability-fit (3-attribute A1/A2/A3) + fit-brief prompt change — replaces the interim `role_fit` bridge; candidate priorities are "V4.2-interim" until this lands
- [ ] (deferred — gated on real capability-fit) Commit 5 — make candidate priority authoritative for `final_priority_level` unless a genuine human override; fix the false "Human Reviewed" labeling and the sticky `reviewed_priority_level` auto-seed
- [ ] (deferred — after Commit 5) Commit 6 — master remediation of already-contaminated derived columns + polluted `reviewed_priority_level`
- [ ] (held — separate track) Data regeneration to fix research integrity issues the audit surfaced: funding-as-commercial (e.g. Solace), mislabeled maturity (e.g. Function Health read late-stage despite Series-B/hypergrowth evidence), and reset field-coverage gaps. The engine logic fixes (A/B) are independent of this.

#### Candidate-engine live verification (Colab — owner: you)
- [ ] Definitive end-to-end golden-master: raw signals → producers → gate, against the live master (the export lacked raw text signals; gate validated 48/48 against recorded producer outputs so far)

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
